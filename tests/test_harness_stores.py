# SPDX-License-Identifier: GPL-3.0-or-later
"""EVERY SCRIPT THAT STARTS THE CHECKOUT'S OWN SERVER POINTS EVERY STORE OF config/ AT ITS TEMPORARY TREE.

    python3 -m unittest tests/test_harness_stores.py

config/ beside the checkout is the owner's own (tests/configguard.py says
what is in it).  The same fault has now been found three times: a suite left
his theme dark; two unit modules went on writing digests.json and wheres.json;
and in a0.5.0 the harnesses behind tests/your_prompts.mjs and
tests/speech_door.mjs wrote his theme into prefs.json again, because the
studio's pages had started to save it (lib/prefs.js) and nobody had told the
two harnesses, which pointed the stores they had thought of and not that one.
Each time a store was redirected in the harness that had leaked and in no
other.  What was missing was a thing that asks, of every harness, about every
store.

WHAT IT DOES.  It reads the files and runs nothing.  The stores are FOUND in
lib/, not listed here (a constant of a module whose path is under "config"
and ends ".json", and a constant that is another module's store by another
name, as newlang.PERSONAL is languages.PERSONAL), so that a store added next
year is asked of every harness the day it is added, and the failure says
the line to put in.  Every script of tests/ that starts the server (it
imports `serve`, or imports one that does) must be named in HARNESSES below.
One that starts the server itself must assign or patch each store; one that
hands the serving to another harness must import it, and that one must do the
assigning.

WHAT IT DOES NOT DO.  It does not see a store whose path a function works
out from a root it is handed (lib/llmconfig.py, lib/updater.py): there is no
constant to point elsewhere.  And it cannot tell that a harness runs before
the server does.  What watches those are the guard around the unit suite
(tests/test_config_untouched.py), the one smoke.py has, and the one release
step 1 puts around the loop of browser suites (tests/configguard.py save and
check): a look at what changed, where this is a look at what was written.
"""
import ast
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
LIB = ROOT / "lib"

# What each script of tests/ that starts the server does about config/: it points
# every store itself ("redirects", or "redirects in NAME" where it is a program
# in a string constant, run by the process it starts); it hands the serving to
# the harness named, which does; or it serves a scratch copy of the toolbox (the
# copy's own lib/ is imported, so the copy's own config/ is the one written).
HARNESSES = {
    "arasaac_harness.py": "redirects",
    "cardkit_harness.py": "redirects",
    "decks_harness.py": "redirects",
    "doclinks_harness.py": "redirects",
    "openfile_harness.py": "redirects",
    "prompts_harness.py": "redirects",
    "smoke.py": "redirects in SERVE_BOOT",
    "speech_harness.py": "redirects",
    "studio_harness.py": "redirects",
    "mobile_harness.py": "cardkit_harness.py",
    "later_harness.py": "mobile_harness.py",
    "outline_harness.py": "mobile_harness.py",
    "making_agent.py": "scratch copy",
}


def _constants(tree):
    """The module-level `NAME = value` statements of a parsed module ->
    [(NAME, value node)]."""
    return [(node.targets[0].id, node.value) for node in tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)]


def stores_of(lib=LIB):
    """Every file the product keeps in config/ whose path is a constant of its
    module -> {(module, NAME)}: what a harness can point elsewhere by assigning
    it."""
    trees = {}
    for path in sorted(Path(lib).glob("*.py")):
        try:
            trees[path.stem] = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            pass
    found = set()
    for module, tree in trees.items():
        for name, value in _constants(tree):
            strings = [n.value for n in ast.walk(value) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            if "config" in strings and any(s.endswith(".json") for s in strings):
                found.add((module, name))
    # A constant that is another module's store by another name (`PERSONAL =
    # languages.PERSONAL`, `from prefs import STORE`) is one more thing to
    # point: assigning the first leaves the copy where it was
    while True:
        more = set()
        for module, tree in trees.items():
            for name, value in _constants(tree):
                if (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                        and (value.value.id, value.attr) in found):
                    more.add((module, name))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        if (node.module, alias.name) in found:
                            more.add((module, alias.asname or alias.name))
        if more <= found:
            return found
        found |= more


def redirected(source):
    """The (module, NAME) pairs a script assigns, or patches for as long as it
    runs -> set.  Comments and strings do not count, only statements:
    `prefs.STORE = ...`, `patch.object(prefs, "STORE", ...)`, `setattr(prefs,
    "STORE", ...)`, wherever they stand in the file."""
    got = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    got.add((target.value.id, target.attr))
        elif isinstance(node, ast.Call) and len(node.args) >= 2:
            call = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            first, second = node.args[0], node.args[1]
            if (call in ("object", "setattr") and isinstance(first, ast.Name)
                    and isinstance(second, ast.Constant) and isinstance(second.value, str)):
                got.add((first.id, second.value))
    return got


def program_in(source, constant):
    """The text of a program a script keeps in a string constant of its own (a
    subprocess is started with it) -> str, "" where there is none."""
    for name, value in _constants(ast.parse(source)):
        if name == constant and isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return ""


def redirecting_source(name, how, tests=TESTS):
    """The text in which a harness's redirecting statements are to be looked for."""
    text = (Path(tests) / name).read_text(encoding="utf-8")
    return program_in(text, how[len("redirects in "):]) if how.startswith("redirects in ") else text


def imports(source, what):
    """Does the script import the module `what`?"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(a.name == what for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == what:
            return True
    return False


def serving_scripts(tests=TESTS):
    """The scripts of tests/ (not the unit modules, which the guard around the
    unit suite watches) that start the server: the ones that import `serve`,
    and the ones that import one of those -> [file name]."""
    sources = {p.stem: p.read_text(encoding="utf-8") for p in Path(tests).glob("*.py") if not p.name.startswith("test_")}
    serving = {stem for stem, text in sources.items() if imports(text, "serve")}
    while True:
        more = {stem for stem, text in sources.items() if stem not in serving and any(imports(text, other) for other in serving)}
        if not more:
            return sorted(stem + ".py" for stem in serving)
        serving |= more


def missing_from(source, stores):
    """What a script has not pointed elsewhere -> ["module.NAME", ...]."""
    got = redirected(source)
    return sorted("%s.%s" % pair for pair in stores if pair not in got)


class TheStoresAreFound(unittest.TestCase):
    def test_the_ones_the_product_keeps_are_among_them(self):
        # a search that found nothing would pass every harness for good: so it is held to what is known to be there
        found = stores_of()
        for pair in [("prefs", "STORE"), ("network", "STORE"), ("prompts", "STORE"), ("offline", "DIGESTS"),
                     ("offline", "WHERES"), ("latexthemes", "STORE"), ("speechconfig", "CONFIG"),
                     ("languages", "PERSONAL"), ("newlang", "PERSONAL")]:
            self.assertIn(pair, found, "%s.%s is a store the product keeps under config/ and the search did not find it" % pair)


class TheHarnesses(unittest.TestCase):
    def test_every_script_that_starts_the_server_is_named_and_every_name_is_one(self):
        found = serving_scripts()
        self.assertEqual(sorted(HARNESSES), found,
                         "a script of tests/ that starts the server has to be named in HARNESSES (and what it does about config/ "
                         "said), and a name there has to be one that does")

    def test_a_harness_that_serves_points_every_store_at_its_temporary_tree(self):
        stores = stores_of()
        said = []
        for name, how in sorted(HARNESSES.items()):
            if not how.startswith("redirects"):
                continue
            lacks = missing_from(redirecting_source(name, how), stores)
            if lacks:
                said.append("tests/%s does not point %s at its temporary tree (a page it serves that saves one writes the "
                            "owner's own config/): `import <module>` and `<module>.<NAME> = str(tmp / \"config\" / \"<file>\")`, "
                            "as tests/decks_harness.py does" % (name, ", ".join(lacks)))
        self.assertEqual(said, [], "\n".join(said))

    def test_a_harness_that_hands_the_serving_on_hands_it_to_one_that_redirects(self):
        for name, how in sorted(HARNESSES.items()):
            seen = [name]
            while not (how.startswith("redirects") or how == "scratch copy"):
                self.assertTrue(imports((TESTS / seen[-1]).read_text(encoding="utf-8"), how[:-3]),
                                "tests/%s hands the serving to %s and does not import it" % (seen[-1], how))
                self.assertIn(how, HARNESSES, "%s is named as the harness that serves for tests/%s and is not in HARNESSES" % (how, seen[-1]))
                self.assertNotIn(how, seen, "tests/%s hands the serving round in a circle: %s" % (name, " -> ".join(seen + [how])))
                seen.append(how)
                how = HARNESSES[how]


class TheCheckItself(unittest.TestCase):
    """DRIVEN ON TEXTS AND ON A FOLDER OF ITS OWN: the check that finds nothing
    wrong in the real files would pass if it could not find anything at all."""

    def lib(self, files):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        for name, text in files.items():
            (Path(td.name) / name).write_text(text, encoding="utf-8")
        return td.name

    def test_a_store_is_a_module_constant_whose_path_is_in_config(self):
        lib = self.lib({
            "alpha.py": 'import os\nSTORE = os.path.join(ROOT, "config", "alpha.json")\n',
            "beta.py": 'from pathlib import Path\nCONFIG = Path(__file__).parent.parent / "config" / "beta.json"\n',
            "gamma.py": 'import os\ndef path(root):\n    return os.path.join(root, "config", "gamma.json")\n',     # worked out by a function
            "delta.py": 'FOLDER = "config"\nNAMES = ("a.json",)\n',                                                  # no path
            "epsilon.py": 'LOG = "/x/config/epsilon.log"\n',                                                      # not a store
        })
        self.assertEqual(stores_of(lib), {("alpha", "STORE"), ("beta", "CONFIG")})

    def test_a_copy_of_a_store_under_another_name_is_one_more_to_point(self):
        lib = self.lib({
            "alpha.py": 'import os\nSTORE = os.path.join(ROOT, "config", "alpha.json")\n',
            "copied.py": 'import alpha\nSAME = alpha.STORE\n',
            "imported.py": 'from alpha import STORE\nfrom alpha import STORE as OTHER\n',
            "chained.py": 'import copied\nAGAIN = copied.SAME\n',
        })
        self.assertEqual(stores_of(lib), {("alpha", "STORE"), ("copied", "SAME"), ("imported", "STORE"), ("imported", "OTHER"), ("chained", "AGAIN")})

    def test_a_script_points_a_store_by_assigning_or_patching_it_and_not_by_saying_so(self):
        source = '''
"""prefs.STORE = "in a docstring" """
import prefs, network
from unittest import mock
# network.STORE = "in a comment"
label = "offline.DIGESTS = in a string"
def serve_it(tmp):
    prefs.STORE = str(tmp / "config" / "prefs.json")
    with mock.patch.object(network, "STORE", "x"):
        pass
    setattr(offline, "WHERES", "y")
'''
        self.assertEqual(redirected(source), {("prefs", "STORE"), ("network", "STORE"), ("offline", "WHERES")})

    def test_a_harness_with_a_store_missing_is_told_which(self):
        # the prompts harness as it was before a0.5.0's step 1 found it: the network and the prompts, and nothing else
        old = ('import network, prompts\n'
               'tmp = make()\n'
               'network.STORE = str(tmp / "config" / "network.json")\n'
               'prompts.STORE = str(tmp / "config" / "prompts.json")\n')
        stores = {("prefs", "STORE"), ("network", "STORE"), ("prompts", "STORE"), ("offline", "DIGESTS")}
        self.assertEqual(missing_from(old, stores), ["offline.DIGESTS", "prefs.STORE"])
        self.assertEqual(missing_from(old + 'prefs.STORE = 1\noffline.DIGESTS = 2\n', stores), [])

    def test_a_program_in_a_string_constant_is_read_as_a_program(self):
        # smoke.py starts serve.py through a boot program it keeps in SERVE_BOOT: the statements there are the redirects,
        # and only in the constant that is named (what the rest of the file says in strings is prose)
        tests = self.lib({"boot.py": 'SERVE_BOOT = """\nimport prefs\nprefs.STORE = "x"\n"""\nPROSE = "network.STORE = y"\n'})
        self.assertEqual(redirected(redirecting_source("boot.py", "redirects in SERVE_BOOT", tests)), {("prefs", "STORE")})
        self.assertEqual(program_in((Path(tests) / "boot.py").read_text(encoding="utf-8"), "NOT_THERE"), "",
                         "a constant that is not there says nothing")

    def test_the_scripts_that_start_the_server_are_found_and_the_unit_modules_are_left_to_their_own_guard(self):
        tests = self.lib({
            "a_harness.py": "import serve\n",
            "b_harness.py": "def go():\n    import serve\n",
            "c_helper.py": "import json\n",
            "test_d.py": "import serve\n",
            "e_harness.py": "from serve import Handler\n",
            "f_harness.py": "def go():\n    import e_harness\n",        # serves through another
            "g_harness.py": "import f_harness\n",                       # and through that one
        })
        self.assertEqual(serving_scripts(tests), ["a_harness.py", "b_harness.py", "e_harness.py", "f_harness.py", "g_harness.py"])


if __name__ == "__main__":
    unittest.main()
