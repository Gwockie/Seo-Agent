"""Explicit stages for one title-only local rehearsal; retained evidence is exclusive."""
import importlib.util
import json
import re
import subprocess
import sys
from hashlib import sha256

from runtime import HERE, OLD, PRIVATE as RUNTIME_PRIVATE, PROJECT, docker, inspect_baseline, inspect_runtime, need, clone, verify_historical_config
from seo_agent.local_title_rehearsal import transition
from seo_agent.post_title_effects import TitleEffect, verify_title_effects
from seo_agent import publication_verification as pv
from seo_agent.page_tracking import extract
from seo_agent.storage import utc_now
from seo_agent.protection import require_protected
from bs4 import BeautifulSoup
from scope import PATHS, CURRENT, PROPOSED, HOME, validate_scope, save_forward
from screening import SIGNING_OPTION, SIGNING_REJECTION, ScreeningRejected, screen_options


PRIVATE = RUNTIME_PRIVATE / 'credential-screening-resume'


def record(name, data):
    with (PRIVATE / (name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)


def inspect_retained_runtime():
    runtime = inspect_runtime()
    retained = json.loads((RUNTIME_PRIVATE/'running-isolation.json').read_text())
    need(runtime == retained, 'Disposable runtime identity differs from the retained rehearsal')
    return runtime


def preflight_command(*, sanitize=False):
    inspect_retained_runtime()
    env = ['-e', 'LSEO_TITLE_SANITIZE=1' if sanitize else 'LSEO_TITLE_SANITIZE=0']
    # Keep raw option input in process memory. The usual Docker failure logger
    # would retain partial stdout on error, so this command has a fixed error.
    try:
        process = subprocess.run(
            ['docker', 'exec', '-i', *env, PROJECT+'-app', 'php',
             '-d', 'display_errors=0', '-d', 'log_errors=0'],
            input=(HERE/'preflight.php').read_bytes(), capture_output=True, timeout=90,
        )
        process.check_returncode()
        return json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError('Local service preflight command failed without a usable response') from None


def preflight():
    verify_historical_config()
    data = preflight_command()
    sys.path.insert(0, str(OLD))
    from screen import inspect as historical_inspect, loads
    from inert_serialized import parse
    # Validate the same two core formats/routes separately from the historical parser.
    options = {row['option_name']: row['option_value'] for row in data.pop('options')}
    need(options.pop('time_format', None) in ('H:i', 'g:i a'), 'Unexpected time format')
    routes = options.pop('rewrite_rules', None)
    need(isinstance(routes, dict) and len(routes) < 1000 and all(
        isinstance(key, str) and len(key) < 1000 and isinstance(value, str) and
        re.fullmatch(r'index\.php\?[A-Za-z0-9_=&$\[\]/.%-]+', value)
        for key, value in routes.items()), 'Unexpected rewrite rule destination')
    try:
        screened = screen_options(options, historical_inspect, parse, loads)
    except ScreeningRejected as exc:
        suffix = '-after-sanitize' if (PRIVATE/'sanitization-attempt.json').exists() else ''
        record('screening-rejection'+suffix, {'observed_utc': utc_now(), **exc.diagnostic})
        print(json.dumps(exc.diagnostic))
        raise SystemExit('Historical options screen rejected the input') from None
    need(options.get(SIGNING_OPTION) == '', 'Expected an existing empty signing option')
    try:
        document = json.loads(data.pop('elementor_data'))
    except ValueError:
        raise ValueError('Invalid representative heading data') from None
    selected = []

    def walk(nodes):
        for node in nodes:
            if node.get('id') == '022c973':
                selected.append(node)
            walk(node.get('elements', []))

    walk(document)
    need(len(selected) == 1, 'Ambiguous representative heading source')
    binding = selected[0]['settings'].get('__dynamic__', {}).get('title', '')
    need('name="post-title"' in binding and 'settings="%7B%7D"' in binding,
         'Heading does not use expected Post Title binding')
    record('preflight', {**data, 'options_screening': screened, 'signing_option_empty': True,
                         'post_title_binding_verified': True, 'observed_utc': utc_now()})


def sanitize():
    verify_historical_config()
    rejection = json.loads((PRIVATE/'screening-rejection.json').read_text())
    need(all(rejection.get(key) == value for key, value in SIGNING_REJECTION.items()),
         'This operation requires the exact observed signing-option rejection')
    need(not any((PRIVATE/name).exists() for name in
                 ('preflight.json', 'baseline-title.json', 'forward-attempt.json', 'restore-attempt.json')),
         'Sanitization must precede the passing preflight, baseline and title attempts')
    baseline = inspect_baseline()
    clone_record = json.loads((RUNTIME_PRIVATE/'clone.json').read_text())
    need(baseline == clone_record['baseline'] and clone('manifest') == clone_record['source_manifest'],
         'Preserved baseline differs from the retained clone record')
    operation = {'location': ['options', SIGNING_OPTION], 'operation': 'clear_existing_scalar_with_update_option'}
    record('sanitization-attempt', {**operation, 'observed_utc': utc_now()})
    outcome = preflight_command(sanitize=True)
    need(outcome == {'signing_option_cleared': True}, 'Sanitization was not confirmed; reconcile before proceeding')
    record('sanitization-result', {**operation, **outcome, 'observed_utc': utc_now()})


def baseline_document_titles():
    titles = []
    for index in range(len(PATHS)):
        soup = BeautifulSoup((PRIVATE/f'before-{index}-raw.html').read_bytes().decode('utf-8'), 'html.parser')
        nodes = soup.select('head > title')
        need(len(nodes) == 1, 'Exactly one baseline document title required')
        titles.append(nodes[0].get_text())
    return titles


def load_scope():
    return validate_scope(json.loads((PRIVATE/'scope.json').read_text()), document_titles=baseline_document_titles())


class Backend:
    def call(self, payload):
        inspect_retained_runtime()
        raw = docker('exec', '-i', PROJECT+'-app', 'php', '/opt/lseo/save-title.php',
                     input=json.dumps(payload).encode(), timeout=90)
        return json.loads(raw)

    def read(self):
        return self.call({'operation': 'read'})['title']

    def save(self, **values):
        return self.call({'operation': 'save', **values})


def capture(label):
    inspect_retained_runtime()
    spec = importlib.util.spec_from_file_location('reviewed_preview', OLD/'preview_proxy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records = []
    for index, path in enumerate(PATHS):
        script = '''import http.client,socket,json,base64
class UnixHTTP(http.client.HTTPConnection):
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
  self.sock.settimeout(45)
  self.sock.connect('/run/lseo-http/app.sock')
conn=UnixHTTP('localhost')
conn.request('GET',PATH,headers={'Host':'127.0.0.1:18718','Accept-Encoding':'identity'})
r=conn.getresponse(); data=r.read(2000001)
assert r.status==200 and len(data)<=2000000
print(json.dumps({'http_status':r.status,'headers':dict(r.getheaders()),'body':base64.b64encode(data).decode()}))
'''.replace('PATH', repr(path))
        observed = json.loads(docker('exec', '-i', PROJECT+'-app', 'python3', '-', input=script.encode(), timeout=90))
        import base64
        raw = base64.b64decode(observed.pop('body'))
        raw.decode('utf-8')  # No replacement decoding of source evidence.
        parser = module.PreviewHTML(path)
        parser.feed(raw.decode('utf-8'))
        parser.close()
        sanitized = ''.join(parser.out).encode('utf-8')
        for kind, content in [('raw', raw), ('sanitized', sanitized)]:
            with (PRIVATE/f'{label}-{index}-{kind}.html').open('xb') as stream:
                stream.write(content)
        records.append({'url': 'http://127.0.0.1:18718'+path, 'checked': utc_now(),
                        **observed, 'raw_sha256': sha256(raw).hexdigest(), 'sanitized_sha256': sha256(sanitized).hexdigest()})
    record(label+'-captures', {'pages': records})


def compare(before_label, after_label, *, current, proposed, reverse=False):
    declaration = load_scope()
    left = json.loads((PRIVATE/(before_label+'-captures.json')).read_text())['pages']
    right = json.loads((PRIVATE/(after_label+'-captures.json')).read_text())['pages']
    need([page['url'] for page in left] == [HOME+path for path in PATHS] and
         [page['url'] for page in right] == [HOME+path for path in PATHS], 'Capture URLs differ from the fixed scope')
    result = []
    for index, page in enumerate(declaration['pages']):
        before = (PRIVATE/f'{before_label}-{index}-sanitized.html').read_bytes()
        after = (PRIVATE/f'{after_label}-{index}-sanitized.html').read_bytes()
        try:
            strict = verify_title_effects(before, after, current=current, proposed=proposed,
                                          effects=[TitleEffect(**v) for v in page['title_effects']])
        except ValueError as exc:
            literal = {'status': 'failed', 'reason': str(exc)}
        else:
            literal = {'status': 'matches_expectation', **strict}
        sources = []
        for label, metadata in [(before_label, left[index]), (after_label, right[index])]:
            html = (PRIVATE/f'{label}-{index}-raw.html').read_bytes().decode('utf-8')
            url = metadata['url']
            payload = {'html': html, 'headers': metadata['headers'], 'values': extract(html, url, metadata['headers']),
                       'http_status': metadata['http_status'], 'final_url': url, 'synthetic': True}
            row = {'id': label, 'url': url, 'checked': metadata['checked'], 'status': 'complete', 'payload': json.dumps(payload)}
            _, source, reason = pv._capture(row, label, url)
            need(source is not None, reason or 'Unusable raw capture')
            sources.append((source, reason))
        effects = []
        for values in page['publication_effects']:
            values = dict(values)
            if reverse:
                values['before'], values['after'] = values['after'], values['before']
            effect = pv.Effect.model_validate(values)
            checked = pv._compare(effect, pv._observe(*sources[0], effect), pv._observe(*sources[1], effect), None)
            effects.append(checked)
        result.append({'url': page['url'], 'literal_title_effects': literal, 'publication_effects': effects})
    record(before_label+'-to-'+after_label+'-verification', {'pages': result})
    need(all(page['literal_title_effects']['status'] == 'matches_expectation' and all(
        effect['status'] == 'matches_expectation' for effect in page['publication_effects']
    ) for page in result), 'Declared rendered effect failed; inspect retained verification')


phase = sys.argv[1] if len(sys.argv) == 2 else ''
need(phase in {'preflight', 'sanitize', 'baseline', 'forward', 'restore', 'verify'}, 'Choose an explicit rehearsal phase')
require_protected(PRIVATE)
backend = Backend()
if phase == 'preflight':
    preflight()
elif phase == 'sanitize':
    sanitize()
elif phase == 'baseline':
    need((PRIVATE/'preflight.json').exists(), 'Passing preflight required before baseline capture')
    record('baseline-title', {'title': backend.read(), 'proposed': PROPOSED,
                             'runtime': inspect_retained_runtime(), 'baseline': inspect_baseline()})
    capture('before')
elif phase == 'forward':
    baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
    need((PRIVATE/'scope.json').exists(), 'Explicit reviewed scope required before mutation')
    need((PRIVATE/'preflight.json').exists(), 'Local service guards and credential screen required before mutation')
    need(baseline['title'] == CURRENT, 'Raw baseline title differs from the fixed test contract')
    result = save_forward(backend, PRIVATE, load_scope(), document_titles=baseline_document_titles())
    print(json.dumps(result))
    need(result['outcome'] == 'applied', 'Forward save not confirmed; do not retry')
    capture('after')
    compare('before', 'after', current=baseline['title'], proposed=PROPOSED)
elif phase == 'restore':
    baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
    result = transition(backend, PRIVATE, 'restore', expected=PROPOSED, replacement=baseline['title'])
    print(json.dumps(result))
    need(result['outcome'] == 'applied', 'Restoration not confirmed; do not overwrite intervening state')
    capture('restored')
    compare('after', 'restored', current=PROPOSED, proposed=baseline['title'], reverse=True)
elif phase == 'verify':
    baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
    raw_title_exact = backend.read() == baseline['title']
    exact = []
    for index, path in enumerate(PATHS):
        before = (PRIVATE/f'before-{index}-sanitized.html').read_bytes()
        restored = (PRIVATE/f'restored-{index}-sanitized.html').read_bytes()
        exact.append({'path': path, 'exact_restoration': before == restored})
    sources = clone('manifest')
    source_unchanged = sources == json.loads((RUNTIME_PRIVATE/'clone.json').read_text())['source_manifest']
    baseline_unchanged = inspect_baseline() == baseline['baseline']
    record('restoration-verified', {'raw_title_exact': raw_title_exact, 'pages': exact,
                                    'baseline_volume_manifests_unchanged': source_unchanged,
                                    'baseline_containers_unchanged': baseline_unchanged,
                                    'runtime': inspect_retained_runtime()})
    need(raw_title_exact and source_unchanged and baseline_unchanged and
         all(page['exact_restoration'] for page in exact), 'Restoration verification failed; inspect retained evidence')
print(json.dumps({'phase': phase, 'status': 'completed'}))
