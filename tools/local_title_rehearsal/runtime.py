"""Fixed disposable Docker route. Never start or write the historical baseline."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

from seo_agent.protection import require_protected
from tools.local_title_rehearsal.locator import checked_path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIVATE = REPO / '.tmp/title-rehearsal-20261117'
HISTORICAL = Path('C:/Personal Projects/seo-agent/local-seo-agent')
OLD = HISTORICAL / '.tmp/meadow-representative-20261021'
SECRETS = HISTORICAL / 'workspace/private/local-staging/meadow-representative-20261021'
BASE = 'lseo-meadow-representative-20261021'
PROJECT = 'lseo-title-rehearsal-20261117'
STABLE_PROJECT = PROJECT + '-stable'
IMAGE = 'sha256:1be23f56b98da527b4fbe2f5fb5974f8edb4ba2e3aafaf304fc1b2238956a8e2'
DBIMAGE = 'percona/percona-server@sha256:fcdd199b34d12c4c5fd3766c7e26e1bf7d8fd5b904c8266a316c864380667231'


def need(value, message):
    if not value:
        raise ValueError(message)


def record(name, data):
    with (PRIVATE / (name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)


def local_docker(*args, **kwargs):
    # A caller's Docker context must never redirect this fixed local route.
    env = {name: value for name, value in os.environ.items() if not name.upper().startswith('DOCKER_')}
    return subprocess.run(
        ['docker', '--host=npipe:////./pipe/dockerDesktopLinuxEngine', *args], env=env, **kwargs,
    )


def docker(*args, input=None, timeout=90, diagnostic_dir=None):
    process = local_docker(*args, input=input, capture_output=True, timeout=timeout)
    if process.returncode:
        if diagnostic_dir is None:
            raise RuntimeError('Docker command failed without usable local evidence')
        import uuid
        name = 'docker-failure-' + uuid.uuid4().hex
        (diagnostic_dir / (name + '.log')).write_bytes(process.stdout + b'\n' + process.stderr)
        raise RuntimeError('Docker failed; private diagnostic ' + name)
    return process.stdout


def inspect_docker(*args):
    """Read-only inspection, including when Docker is stopped or inaccessible."""
    try:
        result = local_docker(*args, capture_output=True, timeout=15, check=True)
        return json.loads(result.stdout)[0]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        raise RuntimeError('Docker inspection unavailable. Check Docker Desktop and the retained containers.') from None


def inspect_baseline():
    result = {}
    for role in ('app', 'db', 'ingress'):
        item = inspect_docker('inspect', BASE + '-' + role + '-1')
        need(not item['State']['Running'], 'Baseline must remain stopped for physical copy')
        need(item['Config']['Labels']['com.docker.compose.project'] == BASE, 'Wrong baseline')
        result[role] = {'id': item['Id'], 'image': item['Image'], 'state': item['State']['Status']}
    return result


def inspect_runtime(*, private=PRIVATE, writer=HERE/'save-title.php', secrets=SECRETS,
                    project=PROJECT, require_running=True):
    result = {}
    for role, image, user, volumes, binds in (
        ('db', DBIMAGE, 'mysql', {'/var/lib/mysql': ('database', True), '/run/lseo-db': ('dbsocket', True)},
         {'/run/secrets/db-root': secrets/'db-root', '/run/secrets/db-user': secrets/'db-user'}),
        ('app', IMAGE, '33:33', {'/var/www/html': ('site', True), '/run/lseo-db': ('dbsocket', False),
                                '/run/lseo-http': ('httpsocket', True)},
         {'/var/www/html/wp-config.php': private/'wp-config.php',
          '/var/www/html/wp-content/mu-plugins/000-local-isolation.php': private/'isolation.php',
          '/opt/lseo/save-title.php': writer,
          '/run/secrets/db-user': secrets/'db-user', '/run/secrets/wp-salts': secrets/'wp-salts'})):
        item = inspect_docker('container', 'inspect', project + '-' + role)
        host, config = item['HostConfig'], item['Config']
        pinned = inspect_docker('image', 'inspect', image)['Id']
        need(item['Image'] == pinned and config['User'] == user, 'Wrong image or runtime user')
        if require_running:
            need(item['State']['Running'] and not item['State']['Paused'],
                 f'Disposable Docker service {role} is stopped or paused')
        need(host['NetworkMode'] == 'none' and not host['PortBindings'] and not item['NetworkSettings']['Ports'], 'Network exposure')
        need(host['ReadonlyRootfs'] and host['CapDrop'] == ['ALL'] and not host.get('CapAdd') and
             not host['Privileged'] and 'no-new-privileges' in host['SecurityOpt'], 'Unsafe capabilities')
        need(host['PidMode'] != 'host' and host['IpcMode'] != 'host', 'Host namespace')
        need(host['RestartPolicy']['Name'] == 'no', 'Unexpected runtime restart policy')
        need(len(item['Mounts']) == len(volumes) + len(binds) and
             {m['Destination'] for m in item['Mounts']} == set(volumes) | set(binds), 'Unexpected mounts')
        for mount in item['Mounts']:
            target = mount['Destination']
            if target in volumes:
                name, writable = volumes[target]
                need(mount['Type'] == 'volume' and mount['Name'] == PROJECT + '_' + name and mount['RW'] == writable, 'Shared or wrong volume')
            else:
                source = mount['Source'].replace('/run/desktop/mnt/host/c/', 'C:/').replace('\\', '/').lower()
                need(mount['Type'] == 'bind' and not mount['RW'] and source == str(binds[target]).replace('\\', '/').lower(), 'Unexpected bind')
        mounts = item['Mounts']
        if project == STABLE_PROJECT:
            mounts = sorted(mounts, key=lambda mount: mount['Destination'])
        result[role] = {'id': item['Id'], 'image': item['Image'], 'network': host['NetworkMode'], 'mounts': mounts}
    return result


def require_exclusive_volumes(*allowed):
    """Ensure no other running container is attached to the retained data or sockets."""
    for role in ('site', 'database', 'dbsocket', 'httpsocket'):
        name = PROJECT + '_' + role
        active = docker('ps', '-q', '--no-trunc', '--filter', 'volume=' + name, timeout=15).decode().splitlines()
        need(set(active) <= set(allowed), 'Another Docker container is using the rehearsal volumes')


def verify_disposable_volumes():
    for role in ('site', 'database', 'dbsocket', 'httpsocket'):
        name = PROJECT + '_' + role
        item = inspect_docker('volume', 'inspect', name)
        need(item['Name'] == name and item['Driver'] == 'local' and item['Scope'] == 'local' and
             not item['Options'] and item['Labels'] == {'lseo.disposable': PROJECT},
             'Wrong retained disposable volume')


def clone(mode, *, diagnostic_dir=PRIVATE, tool=HERE/'clone-volumes.py'):
    args = ['run', '--pull', 'never', '--rm', '--network', 'none', '--read-only', '--user', '0', '--cap-drop', 'ALL',
            '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'CHOWN', '--cap-add', 'FOWNER',
            '--security-opt', 'no-new-privileges']
    for role in ('site', 'database'):
        args += ['--mount', f'type=volume,source={BASE}_{role},target=/source/{role},readonly']
        if mode == 'copy':
            args += ['--mount', f'type=volume,source={PROJECT}_{role},target=/target/{role}']
    args += ['--mount', f'type=bind,source={tool},target=/tool.py,readonly',
             '--entrypoint', 'python3', IMAGE, '/tool.py', mode]
    return json.loads(docker(*args, timeout=180, diagnostic_dir=diagnostic_dir))


def verify_historical_config():
    # Verify historical runtime files retain their independent review seal.
    checked_path(OLD, directory=True)
    seal = json.loads(checked_path(OLD / 'independent-review.json').read_bytes())
    hashes = {p.name: hashlib.sha256(checked_path(p).read_bytes()).hexdigest() for p in OLD.iterdir()
              if p.is_file() and p.suffix in ('.py', '.php', '.yml')}
    need(seal['status'] == 'CLEAN' and seal['files'] == hashes, 'Historical reviewed configuration drift')
    return hashes


def prepare():
    require_protected(PRIVATE)
    require_protected(SECRETS)
    baseline = inspect_baseline()
    need(not docker('ps', '-aq', '--filter', 'name=^/' + PROJECT).strip(), 'Disposable containers already exist')
    need(not docker('volume', 'ls', '-q', '--filter', 'name=' + PROJECT + '_').strip(), 'Disposable volumes already exist')
    hashes = verify_historical_config()
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
    create_services(PROJECT, PRIVATE, HERE/'save-title.php', SECRETS)
    docker('start', PROJECT+'-db', PROJECT+'-app')
    record('running-isolation', inspect_runtime())


def create_services(project, private, writer, secrets):
    """Create the fixed pair on the existing disposable volumes, without starting it."""
    common = ['--pull', 'never', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
              '--security-opt', 'no-new-privileges',
              '--pids-limit', '128', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=128m']
    docker('create', '--name', project+'-db', *common, '--memory', '768m',
           '--env', 'MYSQL_ROOT_PASSWORD_FILE=/run/secrets/db-root', '--env', 'MYSQL_PASSWORD_FILE=/run/secrets/db-user',
           '--env', 'MYSQL_DATABASE=meadow_rep', '--env', 'MYSQL_USER=meadow_rep', '--env', 'PERCONA_TELEMETRY_DISABLE=1',
           '--mount', f'type=bind,source={secrets / "db-root"},target=/run/secrets/db-root,readonly',
           '--mount', f'type=bind,source={secrets / "db-user"},target=/run/secrets/db-user,readonly',
           '--mount', f'type=volume,source={PROJECT}_database,target=/var/lib/mysql',
           '--mount', f'type=volume,source={PROJECT}_dbsocket,target=/run/lseo-db',
           '--tmpfs', '/var/run/mysqld:rw,noexec,nosuid,nodev,size=1m,uid=1001,gid=1001',
           '--tmpfs', '/var/log/mysql:rw,noexec,nosuid,nodev,size=8m,uid=1001,gid=1001',
           DBIMAGE, '--socket=/run/lseo-db/mysql.sock', '--skip-networking', '--mysqlx=OFF',
           '--innodb-buffer-pool-size=128M', '--max-connections=20', '--event-scheduler=DISABLED')
    mounts = [(PROJECT+'_site', '/var/www/html', False, 'volume'),
              (PROJECT+'_dbsocket', '/run/lseo-db', True, 'volume'),
              (PROJECT+'_httpsocket', '/run/lseo-http', False, 'volume'),
              (private/'wp-config.php', '/var/www/html/wp-config.php', True, 'bind'),
              (private/'isolation.php', '/var/www/html/wp-content/mu-plugins/000-local-isolation.php', True, 'bind'),
              (writer, '/opt/lseo/save-title.php', True, 'bind'),
              (secrets/'db-user', '/run/secrets/db-user', True, 'bind'),
              (secrets/'wp-salts', '/run/secrets/wp-salts', True, 'bind')]
    args = ['create', '--name', project+'-app', *common, '--user', '33:33', '--memory', '1536m']
    for source, target, readonly, kind in mounts:
        args += ['--mount', f'type={kind},source={source},target={target}' + (',readonly' if readonly else '')]
    docker(*args, IMAGE)


if __name__ == '__main__':
    import sys
    need(sys.argv[1:] == ['prepare'], 'Only explicit prepare supported here')
    prepare()
    print('Disposable volumes copied and isolated runtime started; baseline remains stopped.')
