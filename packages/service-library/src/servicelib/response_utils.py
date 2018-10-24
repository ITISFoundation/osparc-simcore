from typing import Dict, Tuple

ENVELOPE_KEYS = ('data', 'error')

def unwrap_envelope(payload: Dict) -> Tuple:
    return tuple(payload.get(k) for k in ENVELOPE_KEYS) if payload else (None, None)
