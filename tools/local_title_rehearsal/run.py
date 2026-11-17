"""Explicit stages for one title-only local rehearsal; retained evidence is exclusive."""
import importlib.util
import json
import sys
from hashlib import sha256

from runtime import HERE, OLD, PRIVATE, PROJECT, docker, inspect_baseline, inspect_runtime, need, record, clone
from seo_agent.local_title_rehearsal import transition
from seo_agent.post_title_effects import TitleEffect, verify_title_effects
from seo_agent import publication_verification as pv
from seo_agent.page_tracking import extract
from seo_agent.storage import utc_now
from seo_agent.protection import require_protected

PATHS = ('/psychological-assessments-paoli/', '/contact-us/')
PROPOSED = 'Synthetic Local Title Rehearsal 20261117'


class Backend:
    def call(self, payload):
        inspect_runtime()
        raw = docker('exec', '-i', PROJECT+'-app', 'php', '/opt/lseo/save-title.php',
                     input=json.dumps(payload).encode(), timeout=90)
        return json.loads(raw)

    def read(self):
        return self.call({'operation': 'read'})['title']

    def save(self, **values):
        return self.call({'operation': 'save', **values})


def capture(label):
    inspect_runtime()
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
    declaration = json.loads((PRIVATE/'scope.json').read_text())
    left = json.loads((PRIVATE/(before_label+'-captures.json')).read_text())['pages']
    right = json.loads((PRIVATE/(after_label+'-captures.json')).read_text())['pages']
    result = []
    for index, page in enumerate(declaration['pages']):
        before = (PRIVATE/f'{before_label}-{index}-sanitized.html').read_bytes()
        after = (PRIVATE/f'{after_label}-{index}-sanitized.html').read_bytes()
        strict = verify_title_effects(before, after, current=current, proposed=proposed,
                                     effects=[TitleEffect(**v) for v in page['title_effects']])
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
        result.append({'url': page['url'], 'literal_title_effects': strict, 'publication_effects': effects})
    record(before_label+'-to-'+after_label+'-verification', {'pages': result})
    need(all(effect['status'] == 'matches_expectation' for p in result for effect in p['publication_effects']),
         'Declared raw publication effect failed; inspect retained verification')


phase = sys.argv[1] if len(sys.argv) == 2 else ''
need(phase in {'preflight', 'baseline', 'forward', 'restore', 'verify'}, 'Choose an explicit rehearsal phase')
require_protected(PRIVATE)
backend = Backend()
if phase == 'preflight':
    inspect_runtime()
    raw = docker('exec', '-i', PROJECT+'-app', 'php', input=(HERE/'preflight.php').read_bytes())
    data = json.loads(raw)
    # Historical inert parser rejects credential-shaped values and nonempty secret keys.
    sys.path.insert(0, str(OLD))
    from screen import inspect as screen
    # These two core options are formats/routes, not PHP value containers.
    # Validate their bounded grammar separately rather than weakening the inert parser.
    options = {row['option_name']: row['option_value'] for row in data['options']}
    import re
    need(options.pop('time_format') in ('H:i', 'g:i a'), 'Unexpected time format')
    routes = options.pop('rewrite_rules')
    need(isinstance(routes, dict) and len(routes) < 1000 and all(
        isinstance(key, str) and len(key) < 1000 and isinstance(value, str) and
        re.fullmatch(r'index\.php\?[A-Za-z0-9_=&$\[\]/.%-]+', value)
        for key, value in routes.items()), 'Unexpected rewrite rule destination')
    screened = screen(options)
    document = json.loads(data.pop('elementor_data'))
    selected = []
    def walk(nodes):
        for node in nodes:
            if node.get('id') == '022c973':
                selected.append(node)
            walk(node.get('elements', []))
    walk(document)
    need(len(selected) == 1, 'Ambiguous representative heading source')
    binding = selected[0]['settings'].get('__dynamic__', {}).get('title', '')
    need('name="post-title"' in binding and 'settings="%7B%7D"' in binding, 'Heading does not use expected Post Title binding')
    data.pop('options')
    record('preflight', {**data, 'options_screening': screened, 'post_title_binding': binding,
                         'elementor_data_sha256': sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()})
elif phase == 'baseline':
    record('baseline-title', {'title': backend.read(), 'proposed': PROPOSED,
                             'runtime': inspect_runtime(), 'baseline': inspect_baseline()})
    capture('before')
elif phase == 'forward':
    baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
    need((PRIVATE/'scope.json').exists(), 'Explicit reviewed scope required before mutation')
    need((PRIVATE/'preflight.json').exists(), 'Local service guards and credential screen required before mutation')
    result = transition(backend, PRIVATE, 'forward', expected=baseline['title'], replacement=PROPOSED)
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
    need(backend.read() == baseline['title'], 'Raw title differs from original')
    exact = []
    for index, path in enumerate(PATHS):
        before = (PRIVATE/f'before-{index}-sanitized.html').read_bytes()
        restored = (PRIVATE/f'restored-{index}-sanitized.html').read_bytes()
        need(before == restored, 'Sanitized restored capture differs from baseline')
        exact.append({'path': path, 'sha256': sha256(before).hexdigest(), 'exact_restoration': True})
    sources = clone('manifest')
    need(sources == json.loads((PRIVATE/'clone.json').read_text())['source_manifest'], 'Preserved baseline volume changed')
    need(inspect_baseline() == baseline['baseline'], 'Preserved baseline container changed')
    record('restoration-verified', {'raw_title_exact': True, 'pages': exact, 'baseline_volume_manifests_unchanged': sources,
                                    'runtime': inspect_runtime()})
print(json.dumps({'phase': phase, 'status': 'completed'}))
