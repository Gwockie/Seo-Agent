"""Redacted location for the historical option screen's sensitive-key rejection."""
import re


SIGNING_OPTION = 'mcp_jwt_secret'
SENSITIVE_KEY = re.compile(r'password|passwd|secret|token|api.?key|authorization|webhook|smtp|credential', re.I)
SIGNING_REJECTION = {
    'rule': 'nonempty_sensitive_key',
    'location': ['options', SIGNING_OPTION],
    'value_type': 'str',
}


class ScreeningRejected(ValueError):
    def __init__(self, diagnostic):
        super().__init__('Historical options screen rejected the input')
        self.diagnostic = diagnostic


def screen_options(options, historical_inspect, parse_php, load_json):
    """Keep the historical pass/fail decision and only annotate a rejection."""
    try:
        return historical_inspect(options)
    except ValueError as exc:
        sensitive_key = type(exc) is ValueError and str(exc) == 'Sensitive input key'

    diagnostic = {'rule': 'historical_screen_rejected'}
    if sensitive_key:
        fallback = {'rule': 'nonempty_sensitive_key'}
        try:
            diagnostic = _first_sensitive_key(options, ['options'], parse_php, load_json) or fallback
        except (ValueError, RecursionError):
            diagnostic = fallback
    raise ScreeningRejected(diagnostic)


def _first_sensitive_key(part, path, parse_php, load_json):
    if isinstance(part, dict):
        for index, (key, value) in enumerate(part.items()):
            # Only a static, source-verified option name at its exact path may be printed.
            label = SIGNING_OPTION if path == ['options'] and key == SIGNING_OPTION else f'entry[{index}]'
            location = [*path, label]
            if SENSITIVE_KEY.search(str(key)) and value not in ('', None, False, [], {}):
                return {'rule': 'nonempty_sensitive_key', 'location': location, 'value_type': type(value).__name__}
            problem = (_first_sensitive_key(key, [*location, 'key'], parse_php, load_json) or
                       _first_sensitive_key(value, location, parse_php, load_json))
            if problem:
                return problem
    elif isinstance(part, list):
        for index, value in enumerate(part):
            problem = _first_sensitive_key(value, [*path, f'item[{index}]'], parse_php, load_json)
            if problem:
                return problem
    elif isinstance(part, str):
        trimmed = part.strip(' \t\n\r\x00\x0b')
        if re.match(r'^(?:[a-zA-Z]:|N;)', trimmed):
            return _first_sensitive_key(parse_php(trimmed), [*path, 'php'], parse_php, load_json)
        if trimmed.startswith(('[', '{')):
            try:
                decoded = load_json(trimmed)
            except (ValueError, RecursionError):
                return None
            return _first_sensitive_key(decoded, [*path, 'json'], parse_php, load_json)
    return None
