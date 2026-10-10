"""Workspace-scoped, non-reentrant cross-process coordination gate."""
from contextlib import contextmanager
from pathlib import Path
import os


class BusyError(ValueError):
    pass


def workspace_lock(root):
    # Sibling survives restore into a new directory and is shared by checkouts.
    root = Path(root).resolve()
    return root.parent / (root.name + ".operation.lock")


def is_busy(root):
    try:
        with run_lock(workspace_lock(root)):
            return False
    except BusyError:
        return True


@contextmanager
def run_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        try:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BusyError("Another audit, tracking check, backup or migration is running; retry later") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
