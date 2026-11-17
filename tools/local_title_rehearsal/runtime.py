"""Fixed disposable Docker route. Never start or write the historical baseline."""
import hashlib
import json
import subprocess
from pathlib import Path

from seo_agent.protection import require_protected

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIVATE = REPO / '.tmp/title-rehearsal-20261117'
HISTORICAL = Path('C:/Personal Projects/seo-agent/local-seo-agent')
OLD = HISTORICAL / '.tmp/meadow-representative-20261021'
SECRETS = HISTORICAL / 'workspace/private/local-staging/meadow-representative-20261021'
BASE = 'lseo-meadow-representative-20261021'
PROJECT = 'lseo-title-rehearsal-20261117'
IMAGE = 'sha256:1be23f56b98da527b4fbe2f5fb5974f8edb4ba2e3aafaf304fc1b2238956a8e2'
DBIMAGE = 'percona/percona-server@sha256:fcdd199b34d12c4c5fd3766c7e26e1bf7d8fd5b904c8266a316c864380667231'


def need(value, message):
    if not value:
        raise ValueError(message)


def record(name, data):
    with (PRIVATE / (name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)


def docker(*args, input=None, timeout=90):
    process = subprocess.run(['docker', *args], input=input, capture_output=True, timeout=timeout)
    if process.returncode:
        import uuid
        name = 'docker-failure-' + uuid.uuid4().hex
        (PRIVATE / (name + '.log')).write_bytes(process.stdout + b'\n' + process.stderr)
        raise RuntimeError('Docker failed; private diagnostic ' + name)
    return process.stdout


def inspect_baseline():
    result = {}
    for role in ('app', 'db', 'ingress'):
        item = json.loads(docker('inspect', BASE + '-' + role + '-1'))[0]
        need(not item['State']['Running'], 'Baseline must remain stopped for physical copy')
        need(item['Config']['Labels']['com.docker.compose.project'] == BASE, 'Wrong baseline')
        result[role] = {'id': item['Id'], 'image': item['Image'], 'state': item['State']['Status']}
    return result


def inspect_runtime():
    result = {}
    for role, image, user, volumes, binds in (
        ('db', DBIMAGE, 'mysql', {'/var/lib/mysql': ('database', True), '/run/lseo-db': ('dbsocket', True)},
         {'/run/secrets/db-root': SECRETS/'db-root', '/run/secrets/db-user': SECRETS/'db-user'}),
        ('app', IMAGE, '33:33', {'/var/www/html': ('site', True), '/run/lseo-db': ('dbsocket', False),
                                '/run/lseo-http': ('httpsocket', True)},
         {'/var/www/html/wp-config.php': PRIVATE/'wp-config.php',
          '/var/www/html/wp-content/mu-plugins/000-local-isolation.php': PRIVATE/'isolation.php',
          '/opt/lseo/save-title.php': HERE/'save-title.php',
          '/run/secrets/db-user': SECRETS/'db-user', '/run/secrets/wp-salts': SECRETS/'wp-salts'})):
        item = json.loads(docker('inspect', PROJECT + '-' + role))[0]
        host, config = item['HostConfig'], item['Config']
        pinned = json.loads(docker('image', 'inspect', image))[0]['Id']
        need(item['Image'] == pinned and config['User'] == user, 'Wrong image or runtime user')
        need(item['State']['Running'], 'Disposable service is stopped')
        need(host['NetworkMode'] == 'none' and not host['PortBindings'] and not item['NetworkSettings']['Ports'], 'Network exposure')
        need(host['ReadonlyRootfs'] and host['CapDrop'] == ['ALL'] and not host.get('CapAdd') and
             not host['Privileged'] and 'no-new-privileges' in host['SecurityOpt'], 'Unsafe capabilities')
        need(host['PidMode'] != 'host' and host['IpcMode'] != 'host', 'Host namespace')
        need({m['Destination'] for m in item['Mounts']} == set(volumes) | set(binds), 'Unexpected mounts')
        for mount in item['Mounts']:
            target = mount['Destination']
            if target in volumes:
                name, writable = volumes[target]
                need(mount['Type'] == 'volume' and mount['Name'] == PROJECT + '_' + name and mount['RW'] == writable, 'Shared or wrong volume')
            else:
                source = mount['Source'].replace('/run/desktop/mnt/host/c/', 'C:/').replace('\\', '/').lower()
                need(mount['Type'] == 'bind' and not mount['RW'] and source == str(binds[target]).replace('\\', '/').lower(), 'Unexpected bind')
        result[role] = {'id': item['Id'], 'image': item['Image'], 'network': host['NetworkMode'], 'mounts': item['Mounts']}
    return result


def clone(mode):
    args = ['run', '--rm', '--network', 'none', '--read-only', '--user', '0', '--cap-drop', 'ALL',
            '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'CHOWN', '--cap-add', 'FOWNER',
            '--security-opt', 'no-new-privileges']
    for role in ('site', 'database'):
        args += ['--mount', f'type=volume,source={BASE}_{role},target=/source/{role},readonly']
        if mode == 'copy':
            args += ['--mount', f'type=volume,source={PROJECT}_{role},target=/target/{role}']
    args += ['--mount', f'type=bind,source={HERE / "clone-volumes.py"},target=/tool.py,readonly',
             '--entrypoint', 'python3', IMAGE, '/tool.py', mode]
    return json.loads(docker(*args, timeout=180))


def prepare():
    require_protected(PRIVATE)
    require_protected(SECRETS)
    baseline = inspect_baseline()
    need(not docker('ps', '-aq', '--filter', 'name=^/' + PROJECT).strip(), 'Disposable containers already exist')
    need(not docker('volume', 'ls', '-q', '--filter', 'name=' + PROJECT + '_').strip(), 'Disposable volumes already exist')
    # Verify historical runtime files retain their independent review seal.
    seal = json.loads((OLD / 'independent-review.json').read_text())
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OLD.iterdir()
              if p.is_file() and p.suffix in ('.py', '.php', '.yml')}
    need(seal['status'] == 'CLEAN' and seal['files'] == hashes, 'Historical reviewed configuration drift')
    for name in ('wp-config.php', 'isolation.php'):
        content = (OLD / name).read_text().replace('18717', '18718').replace(
            'meadow-representative-20261021-d0f5a2ec', 'title-rehearsal-20261117')
        with (PRIVATE / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    record('prepare-attempt', {'baseline': baseline, 'historical_config_hashes': hashes})
    for role in ('site', 'database', 'dbsocket', 'httpsocket'):
        docker('volume', 'create', '--label', 'lseo.disposable=' + PROJECT, PROJECT + '_' + role)
    record('clone', {'source_manifest': clone('copy'), 'baseline': inspect_baseline()})
    # New empty socket directories need only their local service ownership.
    docker('run', '--rm', '--network', 'none', '--read-only', '--user', '0', '--cap-drop', 'ALL',
           '--cap-add', 'CHOWN', '--security-opt', 'no-new-privileges',
           '--mount', f'type=volume,source={PROJECT}_dbsocket,target=/dbsocket',
           '--mount', f'type=volume,source={PROJECT}_httpsocket,target=/httpsocket',
           '--entrypoint', 'python3', IMAGE, '-c',
           'import os; os.chown("/dbsocket",1001,1001); os.chown("/httpsocket",33,33)')
    common = ['--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
              '--pids-limit', '128', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=128m']
    docker('run', '-d', '--name', PROJECT+'-db', *common, '--memory', '768m',
           '--env', 'MYSQL_ROOT_PASSWORD_FILE=/run/secrets/db-root', '--env', 'MYSQL_PASSWORD_FILE=/run/secrets/db-user',
           '--env', 'MYSQL_DATABASE=meadow_rep', '--env', 'MYSQL_USER=meadow_rep', '--env', 'PERCONA_TELEMETRY_DISABLE=1',
           '--mount', f'type=bind,source={SECRETS / "db-root"},target=/run/secrets/db-root,readonly',
           '--mount', f'type=bind,source={SECRETS / "db-user"},target=/run/secrets/db-user,readonly',
           '--mount', f'type=volume,source={PROJECT}_database,target=/var/lib/mysql',
           '--mount', f'type=volume,source={PROJECT}_dbsocket,target=/run/lseo-db',
           '--tmpfs', '/var/run/mysqld:rw,noexec,nosuid,nodev,size=1m,uid=1001,gid=1001',
           '--tmpfs', '/var/log/mysql:rw,noexec,nosuid,nodev,size=8m,uid=1001,gid=1001',
           DBIMAGE, '--socket=/run/lseo-db/mysql.sock', '--skip-networking', '--mysqlx=OFF',
           '--innodb-buffer-pool-size=128M', '--max-connections=20', '--event-scheduler=DISABLED')
    mounts = [(PROJECT+'_site', '/var/www/html', False, 'volume'),
              (PROJECT+'_dbsocket', '/run/lseo-db', True, 'volume'),
              (PROJECT+'_httpsocket', '/run/lseo-http', False, 'volume'),
              (PRIVATE/'wp-config.php', '/var/www/html/wp-config.php', True, 'bind'),
              (PRIVATE/'isolation.php', '/var/www/html/wp-content/mu-plugins/000-local-isolation.php', True, 'bind'),
              (HERE/'save-title.php', '/opt/lseo/save-title.php', True, 'bind'),
              (SECRETS/'db-user', '/run/secrets/db-user', True, 'bind'),
              (SECRETS/'wp-salts', '/run/secrets/wp-salts', True, 'bind')]
    args = ['run', '-d', '--name', PROJECT+'-app', *common, '--user', '33:33', '--memory', '1536m']
    for source, target, readonly, kind in mounts:
        args += ['--mount', f'type={kind},source={source},target={target}' + (',readonly' if readonly else '')]
    docker(*args, IMAGE)
    record('running-isolation', inspect_runtime())


if __name__ == '__main__':
    import sys
    need(sys.argv[1:] == ['prepare'], 'Only explicit prepare supported here')
    prepare()
    print('Disposable volumes copied and isolated runtime started; baseline remains stopped.')
