"""Run only in the pinned networkless helper with explicit read-only sources."""
import hashlib
import json
import os
import shutil
import stat
import sys


def manifest(root):
    rows = []
    for parent, directories, files in os.walk(root):
        for name in sorted(directories + files):
            path = os.path.join(parent, name)
            info = os.lstat(path)
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('Nonregular source entry')
            digest = None
            if stat.S_ISREG(info.st_mode):
                with open(path, 'rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            rows.append([os.path.relpath(path, root), info.st_mode, info.st_uid, info.st_gid, digest])
    return hashlib.sha256(json.dumps(sorted(rows), separators=(',', ':')).encode()).hexdigest()


result = {}
for role in ('site', 'database'):
    source, target = '/source/' + role, '/target/' + role
    before = manifest(source)
    if sys.argv[1:] == ['copy']:
        if os.listdir(target):
            raise ValueError('Disposable volume is not empty; do not retry a partial clone')
        shutil.copytree(source, target, dirs_exist_ok=True, copy_function=shutil.copy2)
        # copytree does not preserve ownership; copy it explicitly, including root.
        for parent, directories, files in os.walk(source):
            for path in [parent] + [os.path.join(parent, n) for n in files]:
                info = os.stat(path)
                copied = target + path[len(source):]
                os.chown(copied, info.st_uid, info.st_gid)
        if manifest(target) != before:
            raise ValueError('Clone manifest mismatch')
    if manifest(source) != before:
        raise ValueError('Preserved source changed during reading')
    result[role] = before
print(json.dumps(result))
