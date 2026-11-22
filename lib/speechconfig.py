# SPDX-License-Identifier: GPL-3.0-or-later
"""Small host-persisted speech preferences; no runtime or model management."""
import json
import os  # noqa: F401  (tests patch speechconfig.os.replace: the write goes through storeguard)
from pathlib import Path
import re
import threading

STORE_FORMAT = 1
CONFIG = Path(__file__).resolve().parent.parent / 'config' / 'speech.json'
LOCK = threading.RLock()
LANGUAGE = re.compile(r'^[a-z]{2,3}\Z')


def _selections(raw):
    import speechmodels
    if not isinstance(raw, dict) or len(raw) > 128:
        raise ValueError('Choose one speech model for each language.')
    for lang, model in raw.items():
        if (not isinstance(lang, str) or not LANGUAGE.fullmatch(lang)
                or not isinstance(model, str) or model not in speechmodels.ALLOWED_MODELS
                or not speechmodels.compatible(model, lang)):
            raise ValueError('Choose a listed speech model that supports this language.')
    return dict(raw)


def load(path=None):
    """Read host preferences, or an explicitly isolated fixture's file."""
    path = CONFIG if path is None else Path(path)
    defaults = {'format_version': STORE_FORMAT, 'second_pass': True,
                'models_by_language': {}}
    try:
        if path.stat().st_size > 16384:
            return defaults
        raw = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(raw, dict) or raw.get('format_version') != STORE_FORMAT
                or type(raw.get('second_pass')) is not bool):
            return defaults
        return {'format_version': STORE_FORMAT, 'second_pass': raw['second_pass'],
                'models_by_language': _selections(raw.get('models_by_language', {}))}
    except (OSError, ValueError, TypeError):
        return defaults


def _write(value):
    # an unreadable file there is set aside, never written over (TO-DO §2.29)
    import storeguard
    storeguard.write_json(str(CONFIG), value, ok=lambda d: isinstance(d, dict), indent=None)
    return value


def save(raw):
    allowed = {'second_pass', 'models_by_language'}
    if not isinstance(raw, dict) or not raw or set(raw) - allowed:
        raise ValueError('Choose a speech preference from this page.')
    if 'second_pass' in raw and type(raw['second_pass']) is not bool:
        raise ValueError('Automatic speech checks must be on or off.')
    patch = dict(raw)
    if 'models_by_language' in patch:
        patch['models_by_language'] = _selections(patch['models_by_language'])
    with LOCK:
        value = load()
        value.update(patch)
        return _write(value)


def select(language, model):
    if model == '':
        if not isinstance(language, str) or not LANGUAGE.fullmatch(language):
            raise ValueError('Choose a language for the speech model.')
        selection = {}
    else:
        selection = _selections({language: model})
    with LOCK:
        value = load()
        if model == '':
            value['models_by_language'].pop(language, None)
        value['models_by_language'].update(selection)
        return _write(value)
