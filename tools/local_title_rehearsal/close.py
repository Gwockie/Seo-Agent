"""Retain the blocked run, verify baseline preservation, stop only disposable services."""
import json
from runtime import HERE, PRIVATE, PROJECT, clone, docker, inspect_baseline, inspect_runtime, need, record
from seo_agent.protection import require_protected
from seo_agent.storage import utc_now

require_protected(PRIVATE)
need(not (PRIVATE/'forward-attempt.json').exists() and not (PRIVATE/'restore-attempt.json').exists(),
     'This blocked-run close path must not mask an attempted mutation')
runtime = inspect_runtime()
baseline = json.loads((PRIVATE/'baseline-title.json').read_text())
actual = json.loads(docker('exec', '-i', PROJECT+'-app', 'php', '/opt/lseo/save-title.php',
                          input=b'{"operation":"read"}'))['title']
need(actual == baseline['title'], 'Current raw Title differs; reconcile before stopping')
syntax = {}
for name in ('save-title.php', 'preflight.php'):
    reply = docker('exec', '-i', PROJECT+'-app', 'php', '-l', input=(HERE/name).read_bytes())
    need(b'No syntax errors detected' in reply, 'PHP syntax check failed')
    syntax[name] = 'passed'
source = clone('manifest')
need(source == json.loads((PRIVATE/'clone.json').read_text())['source_manifest'], 'Preserved volume manifest changed')
need(inspect_baseline() == baseline['baseline'], 'Preserved baseline container identity/state changed')
record('blocked-run', {
    'observed_utc': utc_now(), 'status': 'blocked_before_title_mutation',
    'forward': 'not_attempted', 'restoration': 'not_attempted',
    'current_raw_title': actual, 'raw_title_matches_baseline': True,
    'preflight_attempts': [
        {'attempt': 1, 'result': 'rejected', 'reason': 'inert parser rejected serialized plugin objects and core format/route values'},
        {'attempt': 2, 'result': 'rejected', 'reason': 'credential screen rejected a nonempty sensitive key after class-disabled decoding and core grammar checks'}],
    'local_service_probes': 'PHP HTTP/mail/job/indexing checks passed before both screening rejections',
    'production_credentials_excluded': 'unresolved; no further screening or title writes attempted',
    'baseline_volume_manifests_unchanged': source, 'runtime_before_stop': runtime,
    'php_syntax': syntax,
    'capture_scope': ['http://127.0.0.1:18718/psychological-assessments-paoli/', 'http://127.0.0.1:18718/contact-us/'],
    'limitations': ['No actual forward/restore rehearsal', 'No current SiteGround or production cache certificate',
                    'No complete save-hook or affected-page inventory'],
})
docker('stop', PROJECT+'-app', PROJECT+'-db', timeout=90)
states = {}
for name in (PROJECT+'-app', PROJECT+'-db'):
    item = json.loads(docker('inspect', name))[0]
    need(not item['State']['Running'], 'Disposable service still running')
    states[name] = {'id': item['Id'], 'status': item['State']['Status']}
record('resources-stopped', {'observed_utc': utc_now(), 'containers': states,
                            'retained_volumes': [PROJECT+'_'+r for r in ('site', 'database', 'dbsocket', 'httpsocket')],
                            'baseline': inspect_baseline()})
print('Blocked run retained; raw Title unchanged, preserved manifests unchanged, disposable services stopped.')
