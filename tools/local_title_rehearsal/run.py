"""Explicit stages for one title-only local rehearsal; retained evidence is exclusive."""
import importlib.util
import json
import re
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from tools.local_title_rehearsal.runtime import (
    HERE, OLD, clone, docker, inspect_baseline,
    inspect_runtime, need, verify_historical_config,
)
from seo_agent.coordination import BusyError, run_lock
from seo_agent.local_title_rehearsal import DestinationMismatch, recover, require_observed_replacement, transition
from seo_agent.post_title_effects import TitleEffect, verify_title_effects
from seo_agent import publication_verification as pv
from seo_agent.page_tracking import extract
from seo_agent.storage import new_id, utc_now
from seo_agent.protection import require_protected
from bs4 import BeautifulSoup
from tools.local_title_rehearsal.scope import PATHS, CURRENT, PROPOSED, HOME, validate_scope, save_forward
from tools.local_title_rehearsal.screening import SIGNING_OPTION, SIGNING_REJECTION, ScreeningRejected, screen_options


# The existing containers bind files from this checkout. Keep their identity
# and the shared operation lock fixed when the app runs from another checkout.
RETAINED_CHECKOUT = Path.home()/'.codex/worktrees/e369/local-seo-agent'
RUNTIME_PRIVATE = RETAINED_CHECKOUT/'.tmp/title-rehearsal-20261117'
WRITER = RETAINED_CHECKOUT/'tools/local_title_rehearsal/save-title.php'
PRIVATE = RUNTIME_PRIVATE / 'credential-screening-resume'
JOURNAL = RUNTIME_PRIVATE / 'interruption-recovery'


def record(name, data, *, directory=PRIVATE):
    with (directory / (name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)


def inspect_retained_runtime():
    runtime = inspect_runtime(private=RUNTIME_PRIVATE, writer=WRITER)
    retained = json.loads((RUNTIME_PRIVATE/'running-isolation.json').read_text())
    if runtime != retained:
        raise DestinationMismatch('Disposable runtime identity differs from the retained rehearsal')
    return runtime


def preflight_command(*, sanitize=False):
    runtime = inspect_retained_runtime()
    env = ['-e', 'LSEO_TITLE_SANITIZE=1' if sanitize else 'LSEO_TITLE_SANITIZE=0']
    # Keep raw option input in process memory. The usual Docker failure logger
    # would retain partial stdout on error, so this command has a fixed error.
    try:
        process = subprocess.run(
            ['docker', 'exec', '-i', *env, runtime['app']['id'], 'php',
             '-d', 'display_errors=0', '-d', 'log_errors=0'],
            input=(HERE/'preflight.php').read_bytes(), capture_output=True, timeout=90,
        )
        process.check_returncode()
        return json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError('Local service preflight command failed without a usable response') from None


def check_preflight():
    verify_historical_config()
    data = preflight_command()
    sys.path.insert(0, str(OLD))
    try:
        from screen import inspect as historical_inspect, loads
        from inert_serialized import parse
    finally:
        sys.path.remove(str(OLD))
    # Validate the same two core formats/routes separately from the historical parser.
    options = {row['option_name']: row['option_value'] for row in data.pop('options')}
    need(options.pop('time_format', None) in ('H:i', 'g:i a'), 'Unexpected time format')
    routes = options.pop('rewrite_rules', None)
    need(isinstance(routes, dict) and len(routes) < 1000 and all(
        isinstance(key, str) and len(key) < 1000 and isinstance(value, str) and
        re.fullmatch(r'index\.php\?[A-Za-z0-9_=&$\[\]/.%-]+', value)
        for key, value in routes.items()), 'Unexpected rewrite rule destination')
    screened = screen_options(options, historical_inspect, parse, loads)
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
    return {**data, 'options_screening': screened, 'signing_option_empty': True,
            'post_title_binding_verified': True, 'observed_utc': utc_now()}


def preflight():
    try:
        data = check_preflight()
    except ScreeningRejected as exc:
        suffix = '-after-sanitize' if (PRIVATE/'sanitization-attempt.json').exists() else ''
        record('screening-rejection'+suffix, {'observed_utc': utc_now(), **exc.diagnostic})
        print(json.dumps(exc.diagnostic))
        raise SystemExit('Historical options screen rejected the input') from None
    record('preflight', data)


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
    def __init__(self):
        self.bound_destination = None

    def runtime_context(self):
        paths = ('/opt/lseo/save-title.php', '/var/www/html/wp-config.php',
                 '/var/www/html/wp-content/mu-plugins/000-local-isolation.php')
        try:
            runtime = inspect_retained_runtime()
            app = runtime['app']['id']
            checksums = docker('exec', app, 'sha256sum', *paths, diagnostic_dir=None).decode()
        except subprocess.SubprocessError:
            raise RuntimeError('Docker returned no usable runtime evidence') from None
        local = (WRITER, RUNTIME_PRIVATE/'wp-config.php', RUNTIME_PRIVATE/'isolation.php')
        hashes = [sha256(path.read_bytes()).hexdigest() for path in local]
        if checksums.splitlines() != [f'{digest}  {path}' for digest, path in zip(hashes, paths)]:
            raise DestinationMismatch('Mounted source differs from the local rehearsal files')
        context = {'runtime': runtime, 'mount_sha256': hashes, 'page': HOME+PATHS[0], 'post_id': 716}
        identity = sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        if self.bound_destination is not None and self.bound_destination != identity:
            raise DestinationMismatch('Runtime destination changed during the command')
        return app, identity

    def destination(self):
        _, self.bound_destination = self.runtime_context()
        return self.bound_destination

    def call(self, payload):
        app, _ = self.runtime_context()
        try:
            process = subprocess.run(
                ['docker', 'exec', '-i', app, 'php', '-d', 'display_errors=0', '-d', 'log_errors=0',
                 '/opt/lseo/save-title.php'],
                input=json.dumps(payload).encode(), capture_output=True, timeout=90, check=True,
            )
            response = json.loads(process.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            raise RuntimeError('Local WordPress title command returned no usable response') from None
        need(isinstance(response, dict) and response.get('post_id') == 716 and
             response.get('operation') == payload['operation'] and isinstance(response.get('title'), str) and
             isinstance(response.get('epoch'), str) and re.fullmatch(r'[0-9a-f]{64}', response['epoch']),
             'Invalid raw WordPress title response')
        return response

    def read_state(self):
        response = self.call({'operation': 'read'})
        need(response.get('status') == 'read' and response.get('write_attempted') is False,
             'Unexpected WordPress read response')
        return response['title'], response['epoch']

    def read(self):
        title, _ = self.read_state()
        return title

    def save(self, **values):
        response = self.call({'operation': 'save', **values})
        need(response['epoch'] == values['writer_epoch'], 'Save response has the wrong app generation')
        return response


def capture(label, *, directory=PRIVATE):
    runtime = inspect_retained_runtime()
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
        observed = json.loads(docker('exec', '-i', runtime['app']['id'], 'python3', '-', input=script.encode(),
                                     timeout=90, diagnostic_dir=directory))
        import base64
        raw = base64.b64decode(observed.pop('body'))
        raw.decode('utf-8')  # No replacement decoding of source evidence.
        parser = module.PreviewHTML(path)
        parser.feed(raw.decode('utf-8'))
        parser.close()
        sanitized = ''.join(parser.out).encode('utf-8')
        for kind, content in [('raw', raw), ('sanitized', sanitized)]:
            with (directory/f'{label}-{index}-{kind}.html').open('xb') as stream:
                stream.write(content)
        records.append({'url': 'http://127.0.0.1:18718'+path, 'checked': utc_now(),
                        **observed, 'raw_sha256': sha256(raw).hexdigest(), 'sanitized_sha256': sha256(sanitized).hexdigest()})
    record(label+'-captures', {'pages': records}, directory=directory)


def proposed_captures(journal):
    completed = [path for path in journal.glob('proposed-capture-*')
                 if (path/'capture-complete').is_file()]
    if (journal/'after-captures.json').is_file():
        completed.append(journal)
    need(len(completed) <= 1, 'Multiple proposed-state capture bundles; inspect the retained evidence')
    return completed[0] if completed else None


def capture_proposed(journal):
    if proposed_captures(journal) is None:
        directory = journal/f'proposed-capture-{new_id()}'
        directory.mkdir()
        capture('after', directory=directory)
        (directory/'capture-complete').touch(exist_ok=False)


def compare(before_label, after_label, *, current, proposed, journal, reverse=False, verification=None):
    declaration = load_scope()

    def capture_dir(label):
        if label == 'before':
            return PRIVATE
        if label == 'after':
            directory = proposed_captures(journal)
            need(directory is not None, 'Proposed-state capture is unavailable')
            return directory
        return verification or journal

    left = json.loads((capture_dir(before_label)/(before_label+'-captures.json')).read_text())['pages']
    right = json.loads((capture_dir(after_label)/(after_label+'-captures.json')).read_text())['pages']
    need([page['url'] for page in left] == [HOME+path for path in PATHS] and
         [page['url'] for page in right] == [HOME+path for path in PATHS], 'Capture URLs differ from the fixed scope')
    result = []
    for index, page in enumerate(declaration['pages']):
        before = (capture_dir(before_label)/f'{before_label}-{index}-sanitized.html').read_bytes()
        after = (capture_dir(after_label)/f'{after_label}-{index}-sanitized.html').read_bytes()
        need(sha256(before).hexdigest() == left[index]['sanitized_sha256'] and
             sha256(after).hexdigest() == right[index]['sanitized_sha256'], 'Sanitized capture digest differs')
        try:
            strict = verify_title_effects(before, after, current=current, proposed=proposed,
                                          effects=[TitleEffect(**v) for v in page['title_effects']])
        except ValueError as exc:
            literal = {'status': 'failed', 'reason': str(exc)}
        else:
            literal = {'status': 'matches_expectation', **strict}
        sources = []
        for label, metadata in [(before_label, left[index]), (after_label, right[index])]:
            raw = (capture_dir(label)/f'{label}-{index}-raw.html').read_bytes()
            need(sha256(raw).hexdigest() == metadata['raw_sha256'], 'Raw capture digest differs')
            html = raw.decode('utf-8')
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
    record(before_label+'-to-'+after_label+'-verification', {'pages': result}, directory=verification or journal)
    need(all(page['literal_title_effects']['status'] == 'matches_expectation' and all(
        effect['status'] == 'matches_expectation' for effect in page['publication_effects']
    ) for page in result), 'Declared rendered effect failed; inspect retained verification')


def retained_baseline():
    baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
    preflight = json.loads((PRIVATE/'preflight.json').read_text())
    need(baseline['title'] == CURRENT and baseline['proposed'] == PROPOSED and
         baseline['runtime'] == json.loads((RUNTIME_PRIVATE/'running-isolation.json').read_text()),
         'Retained baseline differs from the fixed title or runtime')
    need(all(preflight.get(key) is True for key in ('http_intercepted', 'mail_intercepted', 'jobs_intercepted',
                                                   'signing_option_empty', 'post_title_binding_verified')) and
         preflight.get('local_instance') == 'title-rehearsal-20261117' and str(preflight.get('blog_public')) == '0',
         'Passing retained preflight required')
    need(inspect_baseline() == baseline['baseline'], 'Historical baseline differs from retained evidence')
    return baseline


def verify_restoration(backend, journal, baseline):
    raw_title_exact = backend.read() == baseline['title']
    exact = []
    for index, path in enumerate(PATHS):
        before = (PRIVATE/f'before-{index}-sanitized.html').read_bytes()
        restored = (journal/f'restored-{index}-sanitized.html').read_bytes()
        exact.append({'path': path, 'exact_restoration': before == restored})
    sources = clone('manifest', diagnostic_dir=journal)
    source_unchanged = sources == json.loads((RUNTIME_PRIVATE/'clone.json').read_text())['source_manifest']
    baseline_unchanged = inspect_baseline() == baseline['baseline']
    record('restoration-verified', {'raw_title_exact': raw_title_exact, 'pages': exact,
                                    'baseline_volume_manifests_unchanged': source_unchanged,
                                    'baseline_containers_unchanged': baseline_unchanged,
                                    'runtime': inspect_retained_runtime()}, directory=journal)
    need(raw_title_exact and source_unchanged and baseline_unchanged and
         all(page['exact_restoration'] for page in exact), 'Restoration verification failed; inspect retained evidence')


def verify_rendered_restoration(backend, journal, baseline):
    require_observed_replacement(backend, journal, 'restore', expected=PROPOSED, replacement=CURRENT)
    need(backend.read() == CURRENT, 'An intervening Title prevents restoration verification')
    need(proposed_captures(journal) is not None,
         'Restoration verification incomplete; the proposed-state capture is unavailable')
    # A controller can fail after a save or midway through capturing. Reobserve
    # into a fresh directory and leave every earlier artifact in place.
    verification = journal/f'verification-{new_id()}'
    verification.mkdir()
    capture('restored', directory=verification)
    compare('before', 'after', current=CURRENT, proposed=PROPOSED, journal=journal, verification=verification)
    compare('after', 'restored', current=PROPOSED, proposed=CURRENT, journal=journal,
            reverse=True, verification=verification)
    verify_restoration(backend, verification, baseline)
    return verification.name


def run_phase(args, backend, journal):
    phase = args[0]
    if phase == 'preflight':
        preflight()
    elif phase == 'sanitize':
        sanitize()
    elif phase == 'baseline':
        need((PRIVATE/'preflight.json').exists(), 'Passing preflight required before baseline capture')
        record('baseline-title', {'title': backend.read(), 'proposed': PROPOSED,
                                 'runtime': inspect_retained_runtime(), 'baseline': inspect_baseline()})
        capture('before')
    elif phase == 'recover':
        name = args[1]
        expected, replacement = (CURRENT, PROPOSED) if name == 'forward' else (PROPOSED, CURRENT)
        result = recover(backend, journal, name, expected=expected, replacement=replacement)
        print(json.dumps({k: result[k] for k in ('record', 'observation', 'reason')}))
        need(result['actual'] is not None,
             'Title state unresolved; inspect the journal and verify the original app generation has stopped')
    else:
        baseline = retained_baseline()
        if phase == 'forward':
            result = save_forward(backend, journal, load_scope(), document_titles=baseline_document_titles())
            need(result['outcome'] == 'applied', 'Forward save not confirmed; recover without retrying')
            capture_proposed(journal)
            compare('before', 'after', current=CURRENT, proposed=PROPOSED, journal=journal)
        elif phase == 'restore':
            require_observed_replacement(backend, journal, 'forward', expected=CURRENT, replacement=PROPOSED)
            need(backend.read() == PROPOSED, 'An intervening Title prevents restoration')
            load_scope()
            forward_capture_error = None
            try:
                capture_proposed(journal)
            except (OSError, ValueError, RuntimeError) as exc:
                forward_capture_error = type(exc).__name__
            result = transition(backend, journal, 'restore', expected=PROPOSED, replacement=CURRENT)
            need(result['outcome'] == 'applied', 'Restoration not confirmed; recover without retrying')
            capture('restored', directory=journal)
            if forward_capture_error:
                record('after-capture-unavailable', {'error_type': forward_capture_error}, directory=journal)
                raise ValueError('Raw Title restored and captured; rendered verification incomplete because the proposed-state capture is unavailable')
            if not (journal/'before-to-after-verification.json').exists():
                compare('before', 'after', current=CURRENT, proposed=PROPOSED, journal=journal)
            compare('after', 'restored', current=PROPOSED, proposed=CURRENT, reverse=True, journal=journal)
        elif phase == 'verify':
            verification = verify_rendered_restoration(backend, journal, baseline)
            print(json.dumps({'verification': verification}))
    print(json.dumps({'phase': phase, 'status': 'completed'}))


def main(args, *, backend=None, journal=JOURNAL):
    need((len(args) == 1 and args[0] in {'preflight', 'sanitize', 'baseline', 'forward', 'restore', 'verify'}) or
         (len(args) == 2 and args[0] == 'recover' and args[1] in {'forward', 'restore'}),
         'Choose a rehearsal phase or recover forward / recover restore')
    require_protected(RUNTIME_PRIVATE)
    try:
        with run_lock(RUNTIME_PRIVATE/'.title-operation.lock'):
            if args[0] == 'forward':
                journal.mkdir(exist_ok=True)
            if args[0] in {'forward', 'restore', 'verify', 'recover'}:
                require_protected(journal)
            run_phase(args, backend if backend is not None else Backend(), journal)
    except BusyError:
        raise ValueError('Another local title controller is active; leave its journal intact') from None


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(str(exc))
