# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for the two hosts the ARASAAC pictograms come from (lib/getarasaac.py), on 127.0.0.1:
the API's `GET /v1/pictograms/all/<locale>` and the static host's `/pictograms/<id>/<id>_<size>.png`.

Used by tests/test_getarasaac.py (the downloader against it: carrying on, stopping, an update,
a picture that is cut short) and tests/arasaac_harness.py (the Settings page against it): nothing
here reaches a network, and nothing here is ARASAAC's -- the pictures are two-pixel PNGs.

A WORLD is its pictograms, their words and their dates; a Fake is a server of one.  Everything a
test needs to change under a download is a method of the world (`touch`, `add`, `drop`, `fail`).
It answers HTTP/1.1 with a length on everything, so a client that keeps its connection open keeps
it, `If-Modified-Since` with a 304, and counts what it was asked: `requests`, `connections`,
`user_agents`, and the most requests ever in flight at once.
"""
import email.utils
import http.server
import json
import re
import socketserver
import struct
import threading
import time
import zlib


def png(pid, size):
    """A whole PNG that is different for every id and size: two pixels and a text chunk."""
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00" + bytes([pid % 256, (pid // 256) % 256, size % 256]) * 2)
    note = ("pictogram %d at %d" % (pid, size)).encode()
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", b"Comment\x00" + note)
            + chunk(b"IDAT", pixels) + chunk(b"IEND", b""))


class World:
    def __init__(self, n=12, locales=("en", "fr"), start=2239):
        self.lock = threading.RLock()
        self.dates = {}                         # id -> lastUpdated
        self.times = {}                         # id -> the picture's own modification time
        self.flags = {}                         # id -> {"violence": True, ...}
        self.synsets = {}
        self.words = {loc: {} for loc in locales}
        self.no_picture = set()                 # ids the host answers 404 for
        self.failures = []                      # [(regex of the path, behaviour, times left)]
        self.delay = 0.0
        self.gate = threading.Event()           # the pictures wait here while it is cleared (the harness's `hold`)
        self.gate.set()
        self.when = 1700000000.0
        for i in range(n):
            self.add(start + i * 7)

    def add(self, pid, **words):
        with self.lock:
            self.dates[pid] = "2025-01-%02dT10:00:00.000Z" % (1 + pid % 28)
            self.times[pid] = self.when + pid
            self.synsets[pid] = ["%08d-n" % pid]
            for loc, table in self.words.items():
                table[pid] = [{"keyword": "%s-word-%d" % (loc, pid), "type": 2, "plural": "%s-words-%d" % (loc, pid),
                               "meaning": "a meaning of %d" % pid, "hasLocution": False}]
            for loc, w in words.items():
                self.words[loc][pid] = w

    def drop(self, pid):
        with self.lock:
            for table in (self.dates, self.times, self.flags, self.synsets):
                table.pop(pid, None)
            for t in self.words.values():
                t.pop(pid, None)

    def touch(self, pid, picture=False):
        """The record moved (a keyword was mended), and the picture too when `picture`."""
        with self.lock:
            self.dates[pid] = "2026-09-%02dT09:00:00.000Z" % (1 + pid % 28)
            if picture:
                self.times[pid] += 86400 * 30

    def fail(self, pattern, behaviour, times=1):
        """The next `times` requests whose path matches get `behaviour`: "503", "503-retry",
        "drop", "truncate", "html", "404", "500"."""
        with self.lock:
            self.failures.append([re.compile(pattern), behaviour, times])

    def record(self, pid, loc):
        flags = self.flags.get(pid, {})
        return {"_id": pid, "keywords": list(self.words[loc].get(pid, [])), "schematic": bool(flags.get("schematic")),
                "sex": bool(flags.get("sex")), "violence": bool(flags.get("violence")), "aac": False, "aacColor": False,
                "skin": False, "hair": False, "downloads": 0, "categories": ["a category"], "synsets": self.synsets[pid],
                "tags": ["a tag"], "created": "2020-01-01T00:00:00.000Z", "lastUpdated": self.dates[pid], "desc": ""}


class Fake(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

    def __init__(self, world=None):
        self.world = world or World()
        self.requests = []                      # (method, path, headers as a dict)
        self.connections = 0
        self.user_agents = set()
        self.in_flight = 0
        self.most_in_flight = 0
        self.after = {}                         # path regex -> (n, callable): run on every request once n have matched
        self.lock = threading.RLock()
        super().__init__(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    @property
    def api(self):
        return "http://127.0.0.1:%d/v1" % self.server_address[1]

    @property
    def static(self):
        return "http://127.0.0.1:%d/pictograms" % self.server_address[1]

    def count(self, pattern):
        rx = re.compile(pattern)
        return sum(1 for _m, p, _h in self.requests if rx.search(p))

    def stop(self):
        self.shutdown()
        self.server_close()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        with self.server.lock:
            self.server.connections += 1

    def log_message(self, *a):
        pass

    def do_GET(self):
        srv, world = self.server, self.server.world
        with srv.lock:
            srv.requests.append(("GET", self.path, dict(self.headers)))
            srv.user_agents.add(self.headers.get("User-Agent"))
            srv.in_flight += 1
            srv.most_in_flight = max(srv.most_in_flight, srv.in_flight)
        try:
            if re.search(r"/pictograms/\d+/", self.path):
                world.gate.wait(60)             # held: a test that wants to see the count of them before the first one
            if world.delay:
                time.sleep(world.delay)
            for rx, hook in list(srv.after.items()):
                if re.search(rx, self.path) and srv.count(rx) >= hook[0]:
                    hook[1]()
            self.answer(srv, world)
        finally:
            with srv.lock:
                srv.in_flight -= 1

    def send_body(self, status, body, kind, extra=()):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def answer(self, srv, world):
        path = self.path.split("?", 1)[0]
        with world.lock:
            for f in world.failures:
                if f[2] > 0 and f[0].search(path):
                    f[2] -= 1
                    return self.misbehave(f[1], path)
        m = re.fullmatch(r"/v1/pictograms/all/([a-z]+)", path)
        if m:
            loc = m.group(1)
            if loc not in world.words:
                return self.send_body(400, b'{"error":{"type":"request_validation","message":"not an allowed value"}}',
                                      "application/json")
            with world.lock:
                body = json.dumps([world.record(pid, loc) for pid in sorted(world.dates)]).encode("utf-8")
            return self.send_body(200, body, "application/json; charset=utf-8")
        m = re.fullmatch(r"/pictograms/(\d+)/(\d+)_(\d+)\.png", path)
        if m and m.group(1) == m.group(2):
            pid, size = int(m.group(1)), int(m.group(3))
            with world.lock:
                known = pid in world.dates and pid not in world.no_picture
                stamp = world.times.get(pid)
            if not known or size not in (300, 500, 2500):
                return self.send_body(404, b"not found", "text/plain")
            since = self.headers.get("If-Modified-Since")
            if since:
                try:
                    if email.utils.parsedate_to_datetime(since).timestamp() >= stamp:
                        self.send_response(304)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                except (TypeError, ValueError):
                    pass
            return self.send_body(200, png(pid, size), "image/png",
                                  [("Last-Modified", email.utils.formatdate(stamp, usegmt=True))])
        return self.send_body(404, b"not found", "text/plain")

    def misbehave(self, how, path):
        if how == "drop":
            self.close_connection = True
            self.connection.close()
            return
        if how == "truncate":
            whole = png(int(re.search(r"/(\d+)_", path).group(1)), 300)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(whole)))
            self.end_headers()
            self.wfile.write(whole[:len(whole) // 2])
            self.close_connection = True
            return
        if how == "html":
            return self.send_body(200, b"<html><body>a login page, say</body></html>" * 4, "text/html")
        if how == "404":
            return self.send_body(404, b"not found", "text/plain")
        if how == "503-retry":
            return self.send_body(503, b"busy", "text/plain", [("Retry-After", "7")])
        return self.send_body(int(how.split("-")[0]), b"error", "text/plain")
