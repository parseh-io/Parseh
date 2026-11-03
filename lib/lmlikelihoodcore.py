# SPDX-License-Identifier: GPL-3.0-or-later
"""Numerical causal-text evaluation. No prompting, chat, sampling or tools.

Backend contract: tokenize/decode; begin(tokens) resets all inference state;
logits() predicts the NEXT token; push(token) evaluates that supplied token.
Each scored candidate starts from an independent empty state.
"""
import math
import time
import unicodedata

from lmgguf import ScoringError


def log_probability(logits, token):
    values = list(logits)
    if not values or not 0 <= token < len(values) or any(math.isnan(v) or v == math.inf for v in values):
        raise ScoringError('invalid-logits', 'The model produced invalid numerical logits.')
    peak = max(values)
    if peak == -math.inf or values[token] == -math.inf:
        raise ScoringError('unscorable-token', 'A supplied token has no finite likelihood under this model.')
    return values[token] - peak - math.log(math.fsum(math.exp(v - peak) for v in values))


def punctuation(text):
    a, b = 0, len(text)
    while a < b and unicodedata.category(text[a]).startswith('P'):
        a += 1
    while b > a and unicodedata.category(text[b - 1]).startswith('P'):
        b -= 1
    return text[:a], text[a:b], text[b:]


def replacement(original, raw, model_derived=False):
    if (not isinstance(raw, str) or not raw or raw != raw.strip()
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in raw)):
        raise ScoringError('invalid-candidate', 'The candidate is empty, contains controls, or would alter outside whitespace.')
    if raw == original:
        return original
    left, _, right = punctuation(original)
    a, core, b = punctuation(raw)
    if a not in ('', left) or b not in ('', right) or not core:
        raise ScoringError('punctuation-mismatch', 'The candidate would change punctuation attached to the source span.')
    if model_derived and (any(c.isspace() for c in core) or not lexical(core)):
        raise ScoringError('invalid-boundary', 'The decoded model candidate is not a complete lexical word.')
    return left + core + right


def lexical(text):
    # the middle dot is inside a Catalan word (col·lecció), as an apostrophe or a hyphen is inside others
    return bool(text) and any(c.isalnum() for c in text) and all(
        unicodedata.category(c)[0] in 'LMN' or c in "’'-\u200c\u200d\u00b7" for c in text)


def candidates(word, extra):
    """No top-N/confidence/dictionary/phonetic filtering of ASR candidates."""
    out, by_text = [], {}
    supplied = [(word['text'], {'kind': 'original'}, True)]
    supplied += [(a['text'], dict(kind='whisper', alternative_index=i, evidence=a), True)
                 for i, a in enumerate(word.get('asr_alternatives') or [])]
    supplied += [(x, {'kind': 'lm-beam'}, False) for x in extra]
    for raw, origin, mandatory in supplied:
        error = None
        try:
            value = raw
            if origin['kind'] == 'whisper' and isinstance(raw, str) and raw.strip(' ') != raw:
                # Recognizer word strings can include separator spaces. The
                # mapped source span excludes these; preserve its fixed outside
                # spaces, and retain the EXACT ASR spelling in origin evidence.
                origin['boundary_spaces'] = {'leading': len(raw) - len(raw.lstrip(' ')),
                                             'trailing': len(raw) - len(raw.rstrip(' '))}
                value = raw.strip(' ')
            text = word['text'] if origin['kind'] == 'original' else replacement(word['text'], value, not mandatory)
        except ScoringError as e:
            text, error = raw, e.say
        # Invalid alternatives remain in the coverage ledger, never disappear.
        key = (text, error)
        if key in by_text:
            c = by_text[key]
            c['origins'].append(origin); c['mandatory'] |= mandatory
        else:
            c = {'text': text, 'origins': [origin], 'mandatory': mandatory, 'error': error}
            out.append(c); by_text[key] = c
    return out


def decoded_prefix(backend, tokens):
    return backend.decode_prefix(tokens) if hasattr(backend, 'decode_prefix') else backend.decode(tokens)


def safe_prefix(backend, left, streams):
    """Identical token prefix whose decoded bytes end at/before the target.

Tokenization is of COMPLETE L+c+R for each candidate. tokenizing L is only
used to bound a shared prefix, never to concatenate independently encoded
pieces. Merged boundary tokens are scored as part of the varying suffix.
"""
    prefix = backend.tokenize(left)
    for stream in streams:
        n = 0
        while n < min(len(prefix), len(stream)) and prefix[n] == stream[n]:
            n += 1
        prefix = prefix[:n]
    raw = left.encode('utf-8')
    while prefix and not raw.startswith(decoded_prefix(backend, prefix)):
        prefix.pop()
    return prefix


def evaluate(backend, left, right, entries, check=lambda: None, deadline=None):
    streams = {}
    for i, c in enumerate(entries):
        check()
        c.update(log_likelihood=None, evaluated_tokens=None, rank=None, delta_original=None, applicable=False)
        if c['error']:
            continue
        try:
            streams[i] = backend.tokenize(left + c['text'] + right)
            if not streams[i] or len(streams[i]) > backend.context_tokens:
                raise ScoringError('context-limit', 'This candidate exceeds the configured context limit; it was not scored.')
        except ScoringError as e:
            streams.pop(i, None); c['error'] = e.say
    prefix = safe_prefix(backend, left, list(streams.values())) if streams else []
    for i, c in enumerate(entries):
        check()
        if i not in streams:
            continue
        try:
            if deadline and time.monotonic() >= deadline:
                raise ScoringError('target-timeout', 'This target’s time budget expired before this candidate could be scored.')
            stream = streams[i]
            if not prefix:
                raise ScoringError('first-token-unavailable', 'The tokenizer supplies no identical BOS/prefix before this target. Its first token has no preceding logits; a complete score is unavailable.')
            backend.begin(prefix)
            scores = []
            suffix = stream[len(prefix):]
            for at, token in enumerate(suffix):
                check()
                if deadline and time.monotonic() >= deadline:
                    raise ScoringError('target-timeout', 'This target’s time budget expired during supplied-text evaluation.')
                logits = backend.logits()
                scores.append(backend.log_probability(logits, token) if hasattr(backend, 'log_probability') else log_probability(logits, token))
                # The last supplied token is scored by the preceding logits;
                # no subsequent prediction is needed. Avoid leaving a useless
                # asynchronous final GPU decode behind when resetting context.
                if at + 1 < len(suffix):
                    backend.push(token)
            c.update(log_likelihood=math.fsum(scores), evaluated_tokens=len(scores), applicable=True, error=None)
        except ScoringError as e:
            c['error'] = e.say
    original = next(c for c in entries if any(o['kind'] == 'original' for o in c['origins']))
    scored = sorted((c for c in entries if c['log_likelihood'] is not None), key=lambda c: (-c['log_likelihood'], c['text']))
    rank, last = 0, None
    for i, c in enumerate(scored):
        if last is None or abs(c['log_likelihood'] - last) > 1e-9:
            rank = i + 1
            last = c['log_likelihood']
        c['rank'] = rank
        if original['log_likelihood'] is not None:
            c['delta_original'] = c['log_likelihood'] - original['log_likelihood']
    failed = [c for c in entries if c['mandatory'] and c['log_likelihood'] is None]
    complete = not failed
    return {'candidates': scored + [c for c in entries if c['log_likelihood'] is None],
            'coverage': {'state': 'complete' if complete else 'partial' if scored else 'failed',
                         'mandatory_total': sum(c['mandatory'] for c in entries),
                         'mandatory_scored': sum(c['mandatory'] and c['log_likelihood'] is not None for c in entries),
                         'omitted': [{'text': c['text'], 'origins': c['origins'], 'reason': c['error']} for c in failed]},
            'original_log_likelihood': original['log_likelihood'],
            'tied_best': [c['text'] for c in scored if c['rank'] == 1],
            'winner_scope': 'full candidate set' if complete and all(c['log_likelihood'] is not None for c in entries) else 'evaluated candidates only',
            'excluded_prefix_tokens': len(prefix), 'excluded_prefix_bytes': len(decoded_prefix(backend, prefix)) if prefix else 0,
            'retokenized_preceding_bytes': len(left.encode()) - len(decoded_prefix(backend, prefix)) if prefix else len(left.encode()),
            'score_rule': 'log P(candidate + fixed following context | original preceding context); raw sum, no length normalization'}


def beam_candidates(backend, left, word, config, check, deadline, discovery=None):
    """Deterministic, bounded raw-token beam search; no assistant completion.

A lexical string is complete only after an observed whitespace/punctuation
boundary or EOG. Reaching the token limit is NOT evidence of a word boundary.
UTF-8 partial byte tokens are kept in beams until decodable.
"""
    if not config['candidate_count']:
        return []
    attached, _, _ = punctuation(word['text'])
    # A separately encoded trailing space can be a different token from the
    # leading-space token in a reconstructed word. Start at a safe prefix of
    # the original reconstruction and require the fixed residual context to
    # be reproduced by raw token search before admitting a replacement.
    fixed = (left + attached).encode('utf-8')
    seed = safe_prefix(backend, left + attached, [backend.tokenize(left + word['text'])])
    if not seed:
        return []
    pending = fixed[len(decoded_prefix(backend, seed)):]
    beams, found = [((), 0.0)], []
    for _ in range(config['replacement_tokens'] + 1):
        check()
        if time.monotonic() >= deadline:
            break
        branches = []
        for tokens, summed in beams:
            check()
            backend.begin(seed + list(tokens))
            logits = backend.logits()
            top = backend.top_tokens(logits, config['beam_width']) if hasattr(backend, 'top_tokens') else sorted(range(len(logits)), key=lambda t: (-logits[t], t))[:config['beam_width']]
            for token in top:
                check()
                lp = backend.log_probability(logits, token) if hasattr(backend, 'log_probability') else log_probability(logits, token)
                # A completed path cannot gain probability as more tokens are
                # supplied. This bound prunes only impossible extra search
                # paths; mandatory original/ASR candidates bypass search.
                floor = config.get('minimum_candidate_probability', 0)
                if floor and summed + lp < math.log(floor):
                    continue
                nxt = tokens + (token,)
                raw = backend.decode(nxt)
                if not raw.startswith(pending):
                    if pending.startswith(raw) and len(nxt) <= config['replacement_tokens']:
                        branches.append((nxt, summed + lp))
                    continue
                raw = raw[len(pending):]
                try:
                    decoded = raw.decode('utf-8')
                except UnicodeDecodeError:
                    if len(nxt) <= config['replacement_tokens']:
                        branches.append((nxt, summed + lp))
                    continue
                stripped = decoded.lstrip(' ')
                boundary = next((j for j, c in enumerate(stripped) if c.isspace() or unicodedata.category(c).startswith('P') and c not in "’'-"), None)
                complete = stripped[:boundary] if boundary is not None else stripped if backend.is_eog(token) else None
                if complete and lexical(complete) and len(complete) <= config['replacement_chars']:
                    try:
                        c = replacement(word['text'], complete, True)
                        if math.exp(summed + lp) < config.get('minimum_candidate_probability', 0):
                            continue
                        if config.get('phonetic_filter', False):
                            from lmsound import sound_similarity
                            sound = sound_similarity(punctuation(word['text'])[1], complete, word.get('language', ''))
                            if sound is not None and sound < config.get('phonetic_similarity', .55):
                                continue
                        if c not in found:
                            found.append(c)
                            if discovery is not None:
                                discovery.append({'text': c, 'search_probability': math.exp(summed + lp)})
                    except ScoringError:
                        pass
                if boundary is None and not backend.is_eog(token) and len(nxt) <= config['replacement_tokens'] and len(stripped) <= config['replacement_chars']:
                    branches.append((nxt, summed + lp))
        beams = sorted(branches, key=lambda x: (-x[1], x[0]))[:config['beam_width']]
        if len(found) >= config['candidate_count'] or not beams:
            break
    return found[:config['candidate_count']]


def target(backend, request, config, check=lambda: None):
    started = time.monotonic()
    # Give mandatory supplied-text scoring the whole target budget. Search
    # receives a separate bounded fraction and can never consume that budget.
    extra = []
    discovery = []
    discovery_error = None
    try:
        extra = beam_candidates(backend, request['left'], request['word'], config, check,
                                started + min(20, config['target_seconds'] / 4), discovery)
    except ScoringError as e:
        discovery_error = e.say
    result = evaluate(backend, request['left'], request['right'], candidates(request['word'], extra), check,
                      time.monotonic() + config['target_seconds'])
    result.update(elapsed_seconds=round(time.monotonic() - started, 3), discovery_error=discovery_error,
                  discovery_candidates=discovery[:config['candidate_count']],
                  discovered_candidates=len(extra), discovery_note=None if extra else 'No additional complete replacement was found within the raw-token search bounds.',
                  alternatives_available=request['word'].get('alternatives_available', False),
                  context={'preceding_chars': len(request['left']), 'following_chars': len(request['right']),
                           'preceding': request['left'], 'following': request['right']},
                  search={k: config.get(k) for k in ('beam_width', 'candidate_count', 'replacement_tokens', 'replacement_chars', 'minimum_candidate_probability', 'phonetic_filter', 'phonetic_similarity')})
    return result
