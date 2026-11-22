# SPDX-License-Identifier: GPL-3.0-or-later
"""Host-local scoring settings, independent of all chat adapters."""
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import subprocess
import sys
import threading
import time

from lmgguf import ScoringError, discover, inspect, revalidate, url

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config/lm-likelihood.json'
RUNTIME = ROOT / 'llm-scoring/runtime'
PIN = '0.3.35'
STORE_FORMAT = 1
DEFAULTS = {'format_version': STORE_FORMAT, 'source': 'unsloth', 'manager_url': 'http://127.0.0.1:11434',
            'python': str(RUNTIME / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')),
            'backend': 'cpu', 'gpu_layers': 0, 'gpu_device': 0, 'threads': 4, 'context_tokens': 2048,
            'cuda_host_compiler': '', 'cuda_architectures': 'native', 'cuda_force_mmq': False,
            'preceding_chars': 320, 'following_chars': 160, 'beam_width': 4,
            'candidate_count': 12, 'replacement_tokens': 6, 'replacement_chars': 80,
            'minimum_candidate_probability': 0.1, 'phonetic_filter': True, 'phonetic_similarity': 0.55,
            'target_seconds': 120, 'load_seconds': 180, 'model': None}
BOUNDS = {'gpu_layers': (-1, 1000), 'gpu_device': (0, 63), 'threads': (1, 128), 'context_tokens': (128, 16384),
          'preceding_chars': (0, 8000), 'following_chars': (1, 8000), 'beam_width': (1, 16),
          'candidate_count': (1, 64), 'replacement_tokens': (1, 16),
          'replacement_chars': (1, 200), 'target_seconds': (1, 600), 'load_seconds': (1, 600)}
CATALOG = {}
LOCK = threading.RLock()
INSTALL = {'state': 'not-requested'}


def validate(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS) or raw.get('format_version', 1) != 1:
        raise ScoringError('bad-config', 'These likelihood settings are invalid or use an unknown format.')
    out = dict(DEFAULTS, **raw)
    if out['source'] not in ('unsloth', 'ollama', 'path') or out['backend'] not in ('cpu', 'cuda', 'metal', 'vulkan'):
        raise ScoringError('bad-config', 'Choose a supported model source and runtime backend.')
    out['manager_url'] = url(out['manager_url'])
    p = out['python']
    if not isinstance(p, str) or not os.path.isabs(p) or len(p) > 4096 or any(ord(c) < 32 for c in p):
        raise ScoringError('bad-config', 'The scoring interpreter must be an absolute path on this host.')
    for key, (lo, hi) in BOUNDS.items():
        if type(out[key]) is not int or not lo <= out[key] <= hi:
            raise ScoringError('bad-config', 'A scoring bound is invalid: ' + key + '.')
    if out['backend'] == 'cpu' and out['gpu_layers'] != 0:
        raise ScoringError('bad-config', 'CPU scoring requires zero GPU layers.')
    compiler = out['cuda_host_compiler']
    if not isinstance(compiler, str) or len(compiler) > 4096 or any(ord(c) < 32 for c in compiler) or compiler and not os.path.isabs(compiler):
        raise ScoringError('bad-config', 'The optional CUDA host compiler must be an absolute executable path.')
    architectures = out['cuda_architectures']
    if not isinstance(architectures, str) or len(architectures) > 80 or not re.fullmatch(r'native|[0-9]{2,3}(-real|-virtual)?(;[0-9]{2,3}(-real|-virtual)?)*', architectures):
        raise ScoringError('bad-config', 'CUDA architectures must be native or a semicolon-separated list, such as 75;86 or 61-virtual;80-virtual.')
    if type(out['cuda_force_mmq']) is not bool:
        raise ScoringError('bad-config', 'CUDA force MMQ must be a boolean.')
    if type(out['phonetic_filter']) is not bool:
        raise ScoringError('bad-config', 'The similar-sound filter must be a boolean.')
    for key in ('minimum_candidate_probability', 'phonetic_similarity'):
        if type(out[key]) not in (int, float) or not 0 <= out[key] <= 1:
            raise ScoringError('bad-config', 'A candidate search threshold is invalid.')
    if out['model'] is not None:
        m = out['model']
        if (not isinstance(m, dict) or not isinstance(m.get('identity'), dict)
                or not isinstance(m.get('path'), str) or m['identity'].get('path') != m['path']
                or not isinstance(m.get('model_id'), str) or len(m['model_id']) > 1024):
            raise ScoringError('bad-config', 'The saved model identity is invalid. Discover and select it again.')
        ident = m['identity']
        source_path = m.get('source_path', m['path'])
        if not isinstance(source_path, str) or not os.path.isabs(source_path) or len(source_path) > 4096 or any(ord(c) < 32 for c in source_path):
            raise ScoringError('bad-config', 'The saved model source path is invalid. Discover and select it again.')
        if (set(ident) != {'path', 'size', 'mtime_ns', 'device', 'inode', 'header_sha256'}
                or any(type(ident[k]) is not int or ident[k] < 0 for k in ('size', 'mtime_ns', 'device', 'inode'))
                or not isinstance(ident['header_sha256'], str) or len(ident['header_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in ident['header_sha256']) or not os.path.isabs(m['path'])):
            raise ScoringError('bad-config', 'The saved model identity is incomplete. Discover and select it again.')
    return out


def load():
    try:
        if CONFIG.stat().st_size > 65536:
            return dict(DEFAULTS)
        return validate(json.loads(CONFIG.read_text(encoding='utf-8')))
    except (OSError, ValueError, ScoringError):
        return dict(DEFAULTS)


def revision(config=None):
    return hashlib.sha256(json.dumps(config or load(), sort_keys=True).encode()).hexdigest()


def write(config):
    config = validate(config)
    # an unreadable file there is set aside, never written over (TO-DO §2.29)
    import storeguard
    with LOCK:
        storeguard.write_json(str(CONFIG), config, ok=lambda d: isinstance(d, dict),
                              private=True, indent=None)
    # Cancel active work as soon as settings change, including model loading.
    import lmlikelihood
    lmlikelihood.unload_all()
    return config


def save(body):
    if not isinstance(body, dict) or set(body) - (set(DEFAULTS) - {'model'} | {'path'}):
        raise ScoringError('bad-config', 'Unknown scoring settings were supplied.')
    body = dict(body)
    path = body.pop('path', None)
    config = validate(dict(load(), **body))
    if config['source'] != load()['source']:
        config['model'] = None
    if path is not None:
        if not isinstance(path, str) or not path or len(path) > 4096 or any(ord(c) < 32 for c in path):
            raise ScoringError('bad-config', 'Enter a readable local GGUF path.')
        m = inspect(path)
        m.update(source='path', model_id=m['name'])
        config.update(model=m, source='path')
    return write(config)


def inventory():
    config = load()
    rows, errors = discover(config['source'], config['manager_url']) if config['source'] != 'path' else ([], [])
    with LOCK:
        CATALOG.clear()
        for m in rows:
            ident = hashlib.sha256(json.dumps(m['identity'], sort_keys=True).encode()).hexdigest()
            CATALOG[ident] = m
    return {'models': [{'id': k, 'model_id': m['model_id'], 'architecture': m['architecture'],
                        'bytes': m['identity']['size']} for k, m in CATALOG.items()], 'errors': errors}


def select(ident):
    with LOCK:
        m = CATALOG.get(ident) if isinstance(ident, str) else None
    if m is None:
        raise ScoringError('model-not-found', 'Refresh the host’s installed model inventory before selecting this model.')
    revalidate(m)
    # The native worker still performs architecture compatibility checks;
    # selection rechecks container completeness, not just a catalog snapshot.
    inspect(m['path'])
    return write(dict(load(), model=m, source=m['source']))


_PROBE = {}


def runtime_status(config):
    interpreter = config['python']
    try:
        stamp = (interpreter, os.stat(interpreter).st_mtime_ns)
    except OSError:
        return {'available': False, 'say': 'Install the isolated scoring runtime on the host first.'}
    cached = _PROBE.get(stamp)
    if cached and time.monotonic() - cached[0] < 15:
        return cached[1]
    try:
        p = subprocess.run([interpreter, '-I', str(ROOT / 'lib/lmlikelihoodworker.py'), '--probe'],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
        if p.returncode:
            out = {'available': False, 'say': 'The isolated native runtime stopped during hardware probing. Rebuild it for this CPU/GPU and check driver/library compatibility.'}
            _PROBE[stamp] = (time.monotonic(), out)
            return out
        out = json.loads(p.stdout)
        if out.get('version') != PIN:
            raise ValueError()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        out = {'available': False, 'say': 'The isolated scoring interpreter needs llama-cpp-python ' + PIN + ' and its compatible native library.'}
    _PROBE[stamp] = (time.monotonic(), out)
    return out


def status(host=False):
    config = load()
    error = None
    if config['model']:
        try:
            revalidate(config['model'])
        except ScoringError as e:
            error = e.say
    runtime = {'available': False, 'say': 'The isolated runtime is being rebuilt.'} if INSTALL['state'] == 'installing' else runtime_status(config)
    if config['gpu_layers'] and not any(d.get('backend') == config['backend'] and d.get('index') == config['gpu_device'] for d in runtime.get('gpu_devices', [])):
        runtime = dict(runtime, available=False, say='The selected GPU device is unavailable to this isolated runtime. Check its backend/device and driver, or choose CPU and zero GPU layers.')
    import lmlikelihood
    out = {'configured': bool(config['model']), 'available': bool(config['model']) and not error and runtime.get('available', False),
           'revision': revision(config), 'model': config['model']['model_id'] if config['model'] else None,
           'phonetic_filter': config['phonetic_filter'],
           'runtime': runtime, 'error': error, 'loaded_workers': lmlikelihood.loaded_count(), 'install': dict(INSTALL)}
    if host:
        out['settings'] = config
    return out


def build_flags(config):
    flags = ['-DGGML_NATIVE=on', '-DGGML_CUDA=off', '-DGGML_METAL=off', '-DGGML_VULKAN=off']
    backend = config['backend']
    if backend != 'cpu':
        flags.append('-DGGML_' + backend.upper() + '=on')
    if backend == 'cuda':
        flags.append('-DCMAKE_CUDA_ARCHITECTURES=' + config['cuda_architectures'])
        flags.append('-DGGML_CUDA_FORCE_MMQ=' + ('on' if config['cuda_force_mmq'] else 'off'))
        compiler = config['cuda_host_compiler']
        supplied = ROOT / 'llm-scoring/toolchain/bin/x86_64-conda-linux-gnu-c++'
        if not compiler and supplied.is_file():
            compiler = str(supplied)
        if compiler:
            flags.append('-DCMAKE_CUDA_HOST_COMPILER=' + compiler)
    return ' '.join(shlex.quote(flag) for flag in flags)


def install():
    """Explicit host action: runtime code only, never weights or manager loads."""
    with LOCK:
        if INSTALL['state'] == 'installing':
            return
        INSTALL.clear(); INSTALL.update(state='installing')
    config = load()
    backend = config['backend']
    import lmlikelihood
    lmlikelihood.unload_all()
    def work():
        try:
            import venv
            venv.EnvBuilder(with_pip=True).create(RUNTIME)
            py = RUNTIME / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            env = dict(os.environ, CMAKE_BUILD_PARALLEL_LEVEL='2')
            env['CMAKE_ARGS'] = build_flags(config)
            env['FORCE_CMAKE'] = '1'
            command = [str(py), '-m', 'pip', 'install', '--no-cache-dir', '--force-reinstall',
                       '--no-binary=llama-cpp-python', '-r', str(ROOT / 'lib/lm-scoring-requirements.txt')]
            subprocess.run(command, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=1800)
            with LOCK:
                _PROBE.clear(); INSTALL.update(state='complete', backend=backend)
        except Exception:
            with LOCK:
                INSTALL.update(state='failed', error='The scoring runtime could not be installed. Check Python, the compiler and the selected backend’s build dependencies.')
    threading.Thread(target=work, daemon=True, name='likelihood-runtime-install').start()
