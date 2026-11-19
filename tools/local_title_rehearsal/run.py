"""Explicit stages for one title-only local rehearsal; retained evidence is exclusive."""
import json
import re
import subprocess
import sys
from hashlib import sha256
from types import ModuleType

from tools.local_title_rehearsal.locator import (
    BASELINE_DIR, CLONE_RECORD, REVIEWED_TOOLS, STABLE_ROOT, file_digest, load_registration,
)
from tools.local_title_rehearsal.runtime import (
    HERE, PROJECT, STABLE_PROJECT, clone, docker, inspect_baseline, inspect_docker,
    inspect_runtime, local_docker, need, require_exclusive_volumes,
)
from seo_agent.local_title_rehearsal import DestinationMismatch, forward_binding, recover, require_observed_replacement, transition
from seo_agent.post_title_effects import TitleEffect, verify_title_effects
from seo_agent import publication_verification as pv
from seo_agent.page_tracking import extract
from seo_agent.storage import new_id, utc_now
from bs4 import BeautifulSoup
from tools.local_title_rehearsal.proposal_binding import digest, validate_binding
from tools.local_title_rehearsal.scope import PATHS, CURRENT, PROPOSED, HOME, expected_scope, validate_scope, save_forward
from tools.local_title_rehearsal.screening import SIGNING_OPTION, screen_options


RUNTIME_PRIVATE = STABLE_ROOT
PRIVATE = RUNTIME_PRIVATE / BASELINE_DIR


def record(name, data, *, directory=PRIVATE):
    with (directory / (name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)


def inspect_retained_runtime():
    registration = load_registration(RUNTIME_PRIVATE)
    return inspect_replacement(registration['replacement_runtime'], registration['retired_runtime'])


def inspect_replacement(expected, retired, *, require_running=True):
    runtime = inspect_runtime(private=RUNTIME_PRIVATE, writer=RUNTIME_PRIVATE/'save-title.php',
                              secrets=RUNTIME_PRIVATE/'secrets', project=STABLE_PROJECT,
                              require_running=require_running)
    if runtime != expected:
        raise DestinationMismatch('Disposable runtime identity differs from the registered replacement')
    for role in ('app', 'db'):
        old = inspect_docker('container', 'inspect', PROJECT+'-'+role)
        need(old['Id'] == retired[role]['id'] and old['State']['Status'] == 'exited',
             'Retired rehearsal container identity differs or it is running')
    require_exclusive_volumes(*(item['id'] for item in runtime.values()))
    return runtime


def preflight_command(runtime=None):
    runtime = inspect_retained_runtime() if runtime is None else runtime
    # Keep raw option input in process memory. The usual Docker failure logger
    # would retain partial stdout on error, so this command has a fixed error.
    try:
        process = local_docker(
            'exec', '-i', '-e', 'LSEO_TITLE_SANITIZE=0', runtime['app']['id'], 'php',
            '-d', 'display_errors=0', '-d', 'log_errors=0',
            input=(RUNTIME_PRIVATE/'preflight.php').read_bytes(), capture_output=True, timeout=90,
        )
        process.check_returncode()
        return json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError('Local service preflight command failed without a usable response') from None


def _reviewed_module(name):
    path = RUNTIME_PRIVATE / REVIEWED_TOOLS / (name + '.py')
    module = ModuleType(name)
    exec(compile(path.read_bytes(), str(path), 'exec'), vars(module))
    return module


def check_preflight(runtime=None):
    data = preflight_command(runtime)
    check_heading_binding(data.pop('elementor_data', None))
    inert = _reviewed_module('inert_serialized')
    previous = sys.modules.get('inert_serialized')
    sys.modules['inert_serialized'] = inert
    try:
        screen = _reviewed_module('screen')
    finally:
        if previous is None:
            del sys.modules['inert_serialized']
        else:
            sys.modules['inert_serialized'] = previous
    # Validate the same two core formats/routes separately from the historical parser.
    options = {row['option_name']: row['option_value'] for row in data.pop('options')}
    need(options.pop('time_format', None) in ('H:i', 'g:i a'), 'Unexpected time format')
    routes = options.pop('rewrite_rules', None)
    need(isinstance(routes, dict) and len(routes) < 1000 and all(
        isinstance(key, str) and len(key) < 1000 and isinstance(value, str) and
        re.fullmatch(r'index\.php\?[A-Za-z0-9_=&$\[\]/.%-]+', value)
        for key, value in routes.items()), 'Unexpected rewrite rule destination')
    screened = screen_options(options, screen.inspect, inert.parse, screen.loads)
    need(options.get(SIGNING_OPTION) == '', 'Expected an existing empty signing option')
    return {**data, 'options_screening': screened, 'signing_option_empty': True,
            'post_title_binding_verified': True, 'observed_utc': utc_now()}


def check_heading_binding(raw):
    try:
        document = json.loads(raw)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('Invalid representative heading data') from None
    selected = []
    groups = [document]
    while groups:
        nodes = groups.pop()
        need(isinstance(nodes, list) and all(isinstance(node, dict) for node in nodes),
             'Invalid representative heading data')
        for node in nodes:
            if node.get('id') == '022c973':
                selected.append(node)
            if 'elements' in node:
                groups.append(node['elements'])
    need(len(selected) == 1, 'Ambiguous representative heading source')
    heading = selected[0]
    settings = heading.get('settings')
    dynamic = settings.get('__dynamic__', {}) if isinstance(settings, dict) else None
    need(isinstance(dynamic, dict), 'Invalid representative heading data')
    binding = dynamic.get('title')
    need(heading.get('elType') == 'widget' and heading.get('widgetType') == 'heading' and
         settings.get('header_size') == 'h1' and isinstance(binding, str) and re.fullmatch(
             r'\[elementor-tag id="[a-f0-9]{7}" name="post-title" settings="%7[Bb]%7[Dd]"\]', binding),
         'Heading does not use expected Post Title binding')


def baseline_document_titles(directory=None):
    directory = PRIVATE if directory is None else directory
    titles = []
    for index in range(len(PATHS)):
        soup = BeautifulSoup((directory/f'before-{index}-raw.html').read_bytes().decode('utf-8'), 'html.parser')
        nodes = soup.select('head > title')
        need(len(nodes) == 1, 'Exactly one baseline document title required')
        titles.append(nodes[0].get_text())
    return titles


def load_scope():
    return validate_scope(json.loads((PRIVATE/'scope.json').read_text()), document_titles=baseline_document_titles())


def proposal_scope(replacement):
    return expected_scope(baseline_document_titles(), replacement=replacement)


def baseline_capture_digest():
    return sha256((PRIVATE/'before-captures.json').read_bytes()).hexdigest()


def bound_scope(binding):
    validate_binding(binding)
    scope = proposal_scope(binding['replacement'])
    need(binding['scope_sha256'] == digest(scope) and binding['baseline_captures_sha256'] == baseline_capture_digest(),
         'The rehearsal changed: retained verification scope or baseline evidence differs')
    return scope


def check_literal_replacement(binding):
    """Reject transitions that the retained literal evidence cannot verify in both directions."""
    for index, page in enumerate(bound_scope(binding)['pages']):
        before = (PRIVATE/f'before-{index}-sanitized.html').read_bytes()
        replacement = binding['replacement']
        after = before.replace(CURRENT.encode('utf-8'), replacement.encode('utf-8'))
        effects = [TitleEffect(**rule) for rule in page['title_effects']]
        try:
            verify_title_effects(before, after, current=CURRENT, proposed=replacement, effects=effects)
            verify_title_effects(after, before, current=replacement, proposed=CURRENT, effects=effects)
        except ValueError:
            raise ValueError('Unsupported local Title text for the retained literal verification.') from None


class Backend:
    def __init__(self):
        self.bound_destination = None

    def runtime_context(self):
        try:
            runtime = inspect_retained_runtime()
            hashes = verify_runtime_mounts(runtime, RUNTIME_PRIVATE, RUNTIME_PRIVATE/'save-title.php',
                                           RUNTIME_PRIVATE/'secrets')
        except subprocess.SubprocessError:
            raise RuntimeError('Docker returned no usable runtime evidence') from None
        identity = destination_digest(runtime, hashes)
        if self.bound_destination is not None and self.bound_destination != identity:
            raise DestinationMismatch('Runtime destination changed during the command')
        return runtime['app']['id'], identity

    def destination(self):
        _, self.bound_destination = self.runtime_context()
        return self.bound_destination

    def read_state(self):
        app, _ = self.runtime_context()
        response = read_only_state(app)
        check_heading_binding(response['elementor_data'])
        return response['title'], response['epoch']

    def read(self):
        title, _ = self.read_state()
        return title

    def save(self, **values):
        app, _ = self.runtime_context()
        response = title_command(app, {'operation': 'save', **values})
        need(response['epoch'] == values['writer_epoch'], 'Save response has the wrong app generation')
        return response


def destination_digest(runtime, hashes):
    context = {'runtime': runtime, 'mount_sha256': hashes, 'page': HOME+PATHS[0], 'post_id': 716}
    return sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def verify_runtime_mounts(runtime, private, writer, secrets, *, historical=False):
    app_files = {
        '/opt/lseo/save-title.php': writer,
        '/var/www/html/wp-config.php': private/'wp-config.php',
        '/var/www/html/wp-content/mu-plugins/000-local-isolation.php': private/'isolation.php',
    }
    db_files = {}
    if not historical:
        app_files.update({'/run/secrets/db-user': secrets/'db-user', '/run/secrets/wp-salts': secrets/'wp-salts'})
        db_files.update({'/run/secrets/db-root': secrets/'db-root', '/run/secrets/db-user': secrets/'db-user'})
    hashes = []
    for role, files in (('app', app_files), ('db', db_files)):
        if not files:
            continue
        expected = [file_digest(path) for path in files.values()]
        checksums = docker('exec', runtime[role]['id'], 'sha256sum', *files, diagnostic_dir=None).decode()
        if checksums.splitlines() != [f'{value}  {path}' for path, value in zip(files, expected)]:
            raise DestinationMismatch('Mounted source differs from the local rehearsal files')
        hashes.extend(expected)
    return hashes


def read_only_state(app):
    try:
        process = local_docker(
            'exec', '-i', app, 'php', '-d', 'display_errors=0', '-d', 'log_errors=0',
            input=(HERE/'read-state.php').read_bytes(), capture_output=True, timeout=90, check=True,
        )
        response = json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise RuntimeError('Local read-only Title inspection returned no usable response') from None
    need(isinstance(response, dict), 'Local read-only Title inspection returned no usable response')
    if response.get('blocker') == 'isolation':
        raise ValueError('Local database isolation differs from the rehearsal')
    if response.get('blocker') == 'page':
        raise ValueError('Local Title page identity differs from the rehearsal')
    if response.get('blocker') == 'signing_option':
        raise ValueError('Expected an existing empty signing option')
    need(response.get('post_id') == 716 and isinstance(response.get('title'), str) and
         isinstance(response.get('epoch'), str) and re.fullmatch(r'[0-9a-f]{64}', response['epoch']) and
         'elementor_data' in response, 'Local read-only Title inspection returned no usable response')
    return response


def title_command(app, payload):
    try:
        process = local_docker(
            'exec', '-i', app, 'php', '-d', 'display_errors=0', '-d', 'log_errors=0',
            '/opt/lseo/save-title.php', input=json.dumps(payload).encode(), capture_output=True, timeout=90, check=True,
        )
        response = json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise RuntimeError('Local WordPress title command returned no usable response') from None
    need(isinstance(response, dict) and response.get('post_id') == 716 and
         response.get('operation') == payload['operation'] and isinstance(response.get('title'), str) and
         isinstance(response.get('epoch'), str) and re.fullmatch(r'[0-9a-f]{64}', response['epoch']),
         'Invalid raw WordPress title response')
    return response


def capture(label, *, directory=PRIVATE, runtime=None):
    if runtime is None:
        runtime = inspect_retained_runtime()
        verify_runtime_mounts(runtime, RUNTIME_PRIVATE, RUNTIME_PRIVATE/'save-title.php', RUNTIME_PRIVATE/'secrets')
    module = _reviewed_module('preview_proxy')
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


def compare(before_label, after_label, *, current, proposed, journal, reverse=False, verification=None, binding=None):
    declaration = bound_scope(binding) if binding is not None else load_scope()

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
    record(before_label+'-to-'+after_label+'-verification', {'pages': result, **binding_reference(binding)},
           directory=verification or journal)
    need(all(page['literal_title_effects']['status'] == 'matches_expectation' and all(
        effect['status'] == 'matches_expectation' for effect in page['publication_effects']
    ) for page in result), 'Declared rendered effect failed; inspect retained verification')


def retained_baseline():
    baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
    preflight = json.loads((PRIVATE/'preflight.json').read_text())
    need(baseline['title'] == CURRENT and baseline['proposed'] == PROPOSED and
         baseline['runtime'] == load_registration(RUNTIME_PRIVATE)['replacement_runtime'],
         'Retained baseline differs from the fixed title or runtime')
    need(all(preflight.get(key) is True for key in ('http_intercepted', 'mail_intercepted', 'jobs_intercepted',
                                                   'signing_option_empty', 'post_title_binding_verified')) and
         preflight.get('local_instance') == 'title-rehearsal-20261117' and str(preflight.get('blog_public')) == '0',
         'Passing retained preflight required')
    need(inspect_baseline() == baseline['baseline'], 'Historical baseline differs from retained evidence')
    return baseline


def binding_reference(binding):
    return {'proposal_binding_sha256': digest(binding)} if binding is not None else {}


def verify_restoration(backend, journal, baseline, *, binding=None):
    raw_title_exact = backend.read() == baseline['title']
    exact = []
    for index, path in enumerate(PATHS):
        before = (PRIVATE/f'before-{index}-sanitized.html').read_bytes()
        restored = (journal/f'restored-{index}-sanitized.html').read_bytes()
        exact.append({'path': path, 'exact_restoration': before == restored})
    sources = clone('manifest', diagnostic_dir=journal, tool=RUNTIME_PRIVATE/'clone-volumes.py')
    source_unchanged = sources == json.loads((RUNTIME_PRIVATE/CLONE_RECORD).read_text())['source_manifest']
    baseline_unchanged = inspect_baseline() == baseline['baseline']
    record('restoration-verified', {'raw_title_exact': raw_title_exact, 'pages': exact,
                                    'baseline_volume_manifests_unchanged': source_unchanged,
                                    'baseline_containers_unchanged': baseline_unchanged,
                                    'runtime': inspect_retained_runtime(), **binding_reference(binding)}, directory=journal)
    need(raw_title_exact and source_unchanged and baseline_unchanged and
         all(page['exact_restoration'] for page in exact), 'Restoration verification failed; inspect retained evidence')


def verify_rendered_restoration(backend, journal, baseline, *, replacement=PROPOSED, binding=None):
    require_observed_replacement(backend, journal, 'restore', expected=replacement, replacement=CURRENT)
    need(backend.read() == CURRENT, 'An intervening Title prevents restoration verification')
    need(proposed_captures(journal) is not None,
         'Restoration verification incomplete; the proposed-state capture is unavailable')
    # A controller can fail after a save or midway through capturing. Reobserve
    # into a fresh directory and leave every earlier artifact in place.
    verification = journal/f'verification-{new_id()}'
    verification.mkdir()
    capture('restored', directory=verification)
    compare('before', 'after', current=CURRENT, proposed=replacement, journal=journal,
            verification=verification, binding=binding)
    compare('after', 'restored', current=replacement, proposed=CURRENT, journal=journal,
            reverse=True, verification=verification, binding=binding)
    verify_restoration(backend, verification, baseline, binding=binding)
    return verification.name


def run_phase(args, backend, journal, *, binding=None):
    phase = args[0]
    if phase in ('recover', 'restore', 'verify'):
        binding = forward_binding(journal)
    if binding is not None:
        validate_binding(binding)
    replacement = binding['replacement'] if binding is not None else PROPOSED
    if phase == 'recover':
        name = args[1]
        expected, target = (CURRENT, replacement) if name == 'forward' else (replacement, CURRENT)
        result = recover(backend, journal, name, expected=expected, replacement=target)
        print(json.dumps({k: result[k] for k in ('record', 'observation', 'reason')}))
        need(result['actual'] is not None,
             'Title state unresolved; inspect the journal and verify the original app generation has stopped')
    else:
        baseline = retained_baseline()
        if phase == 'forward':
            declaration = bound_scope(binding) if binding is not None else load_scope()
            result = save_forward(backend, journal, declaration, document_titles=baseline_document_titles(), binding=binding)
            need(result['outcome'] == 'applied', 'Forward save not confirmed; recover without retrying')
            capture_proposed(journal)
            compare('before', 'after', current=CURRENT, proposed=replacement, journal=journal, binding=binding)
        elif phase == 'restore':
            require_observed_replacement(backend, journal, 'forward', expected=CURRENT, replacement=replacement)
            need(backend.read() == replacement, 'An intervening Title prevents restoration')
            if binding is not None:
                bound_scope(binding)
            else:
                load_scope()
            forward_capture_error = None
            try:
                capture_proposed(journal)
            except (OSError, ValueError, RuntimeError) as exc:
                forward_capture_error = type(exc).__name__
            result = transition(backend, journal, 'restore', expected=replacement, replacement=CURRENT)
            need(result['outcome'] == 'applied', 'Restoration not confirmed; recover without retrying')
            capture('restored', directory=journal)
            if forward_capture_error:
                record('after-capture-unavailable', {'error_type': forward_capture_error}, directory=journal)
                raise ValueError('Raw Title restored and captured; rendered verification incomplete because the proposed-state capture is unavailable')
            if not (journal/'before-to-after-verification.json').exists():
                compare('before', 'after', current=CURRENT, proposed=replacement, journal=journal, binding=binding)
            compare('after', 'restored', current=replacement, proposed=CURRENT, reverse=True, journal=journal, binding=binding)
        elif phase == 'verify':
            verification = verify_rendered_restoration(backend, journal, baseline, replacement=replacement, binding=binding)
            print(json.dumps({'verification': verification}))
    print(json.dumps({'phase': phase, 'status': 'completed'}))


if __name__ == '__main__':
    sys.exit('Use the explicitly enabled loopback app for saved-proposal rehearsal and recovery.')
