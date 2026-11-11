"""Bounded, inert code-archive manifests. No extraction, execution or approval.

Callers supply the separately approved relative paths and an independently retained
archive digest. A successful result describes these bytes, not live equivalence,
absence of credentials, installed activation or a publisher certificate.
"""
from dataclasses import dataclass
import binascii
import hashlib
import json
from pathlib import Path
import re
import stat
import struct
import unicodedata
import zipfile
import zlib


@dataclass(frozen=True)
class Limits:
    archive_bytes: int = 2_000_000_000
    source_bytes: int = 1_500_000_000
    file_bytes: int = 256_000_000
    entries: int = 60_000
    central_bytes: int = 32_000_000
    compression_ratio: int = 1000
    path_depth: int = 32
    tree_nodes: int = 60_000
    tree_path_bytes: int = 8_000_000


def _path(value):
    if (not isinstance(value, str) or not value or len(value) > 4096 or value.endswith('/')
            or any(c in value for c in ('\\', ':', '\x00'))
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)
            or len(value.split('/')) > 32
            or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in value.split('/'))):
        raise ValueError('Archive paths must be explicit safe relative paths')
    return value


def _key(path):
    # Refuse aliases before any future Windows extraction can collapse them.
    return unicodedata.normalize('NFC', path).casefold()


def _portable(path):
    for component in path.split('/'):
        if (any(c in component for c in '<>"|?*')
                or re.fullmatch(r'(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])', component.split('.')[0].rstrip(' '), re.I)):
            raise ValueError('Archive name is not portable to Windows')


def _extra(raw):
    position = 0
    while position < len(raw):
        if len(raw) - position < 4:
            raise ValueError('Malformed ZIP extra field')
        kind, size = struct.unpack_from('<HH', raw, position)
        position += 4 + size
        if position > len(raw) or kind in (0x0001, 0x7075):
            raise ValueError('Unsupported ZIP64 or alternate path encoding')


def _digest(handle):
    handle.seek(0)
    return hashlib.file_digest(handle, 'sha256').hexdigest()


def _directory_bound(handle, size, limits):
    # Bound the central directory before ZipFile allocates an entry for every row.
    # Source collections are below ZIP64 limits; unsupported ZIP64/multipart
    # archives require a separate collector rather than an unbounded fallback.
    handle.seek(max(0, size - 65_557))
    tail = handle.read(65_557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError('Archive end record missing')
    _, disk, directory_disk, disk_count, count, length, start, comment = struct.unpack(
        '<4s4H2LH', tail[offset:offset + 22])
    end_offset = size - len(tail) + offset
    if (disk or directory_disk or disk_count != count or count == 65_535
            or start == 0xFFFFFFFF or length == 0xFFFFFFFF
            or not 0 < count <= limits.entries or not count * 46 <= length <= limits.central_bytes
            or start + length != end_offset or offset + 22 + comment != len(tail)):
        raise ValueError('Archive directory exceeds bounds or uses an unsupported layout')
    # Do not trust the declared EOCD count to bound ZipFile's allocation.
    handle.seek(start)
    position, actual = start, 0
    while position < end_offset:
        header = handle.read(46)
        if len(header) != 46 or header[:4] != b'PK\x01\x02':
            raise ValueError('Malformed central directory')
        if struct.unpack_from('<H', header, 34)[0]:
            raise ValueError('Multipart archive member is unsupported')
        name_size, extra_size, comment_size = struct.unpack_from('<HHH', header, 28)
        position += 46 + name_size + extra_size + comment_size
        actual += 1
        if position > end_offset or actual > limits.entries:
            raise ValueError('Actual central directory exceeds bounds')
        handle.seek(position)
    if actual != count:
        raise ValueError('Actual central directory count disagrees with its declaration')
    return count, start


def _member(handle, info, cursor, central_start, limits):
    if info.header_offset != cursor:
        raise ValueError('Unindexed or overlapping local archive records')
    handle.seek(cursor)
    header = handle.read(30)
    if len(header) != 30 or header[:4] != b'PK\x03\x04':
        raise ValueError('Malformed local archive record')
    _, version, flags, method, _, _, crc, compressed, size, name_size, extra_size = struct.unpack('<4s5H3L2H', header)
    if (version > 20 or flags != info.flag_bits or flags & ~(0x800 | 8 | 6)
            or method != info.compress_type or compressed == 0xFFFFFFFF or size == 0xFFFFFFFF
            or cursor + 30 + name_size + extra_size + info.compress_size > central_start):
        raise ValueError('Unsupported or inconsistent local archive header')
    name = handle.read(name_size).decode('utf8' if flags & 0x800 else 'cp437')
    if name != info.orig_filename:
        raise ValueError('Local and central archive names disagree')
    _extra(handle.read(extra_size))
    if not flags & 8 and (crc, compressed, size) != (info.CRC, info.compress_size, info.file_size):
        raise ValueError('Local and central archive lengths or CRC disagree')
    if method == zipfile.ZIP_STORED and info.compress_size != info.file_size:
        raise ValueError('Stored archive lengths disagree')
    digest, actual_size, actual_crc = hashlib.sha256(), 0, 0
    inflater = zlib.decompressobj(-15) if method == zipfile.ZIP_DEFLATED else None
    def consume(block):
        nonlocal actual_size, actual_crc
        actual_size += len(block)
        if actual_size > info.file_size or actual_size > limits.file_bytes:
            raise ValueError('Archive member expanded beyond declared bounds')
        digest.update(block)
        actual_crc = binascii.crc32(block, actual_crc)
    remaining = info.compress_size
    while remaining:
        block = handle.read(min(65_536, remaining))
        if not block:
            raise ValueError('Truncated archive payload')
        remaining -= len(block)
        if inflater is None:
            consume(block)
        else:
            while block:
                consume(inflater.decompress(block, 65_536))
                if inflater.unused_data:
                    raise ValueError('Trailing bytes after deflate payload')
                block = inflater.unconsumed_tail
    if inflater is not None:
        while block := inflater.decompress(b'', 65_536):
            consume(block)
        if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            raise ValueError('Incomplete deflate payload')
    if actual_size != info.file_size or actual_crc != info.CRC:
        raise ValueError('Archive integrity validation failed')
    if flags & 8:
        first = handle.read(4)
        descriptor = handle.read(12) if first == b'PK\x07\x08' else first + handle.read(8)
        if len(descriptor) != 12 or struct.unpack('<3L', descriptor) != (info.CRC, info.compress_size, info.file_size):
            raise ValueError('Archive descriptor disagrees with its directory')
    if handle.tell() > central_start:
        raise ValueError('Archive record overlaps central directory')
    return digest.hexdigest(), actual_size, handle.tell()


def manifest_archive(path, *, expected_sha256, prefix, directories, files, limits=Limits(), path_semantics='portable'):
    """Hash one exact archive against an explicit source allowlist, without writes.

    ``prefix`` is the single ZIP wrapper directory. ``directories`` and ``files``
    are nonempty relative paths beneath it. Every approved item must be present;
    only ancestor directory entries may appear outside recursive code roots.
    Directory roots include all packaged descendants. Do not use this function
    to imply a selective descendant exclusion that the collection did not enforce.
    Explicit ``posix`` semantics preserve case-sensitive source names; their
    manifest does not authorize extraction onto a case-insensitive filesystem.
    """
    if not isinstance(expected_sha256, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha256):
        raise ValueError('An exact retained SHA256 is required')
    if path_semantics not in ('portable', 'posix'):
        raise ValueError('Choose explicit portable or posix path semantics')
    identity = _key if path_semantics == 'portable' else lambda p: p
    prefix = _path(prefix)
    if '/' in prefix or not isinstance(directories, (list, tuple)) or not isinstance(files, (list, tuple)):
        raise ValueError('Use one wrapper name and explicit path lists')
    directories, files = tuple(directories), tuple(files)
    approved = tuple(_path(p) for p in directories + files)
    if (not approved or len(approved) > 500 or len({identity(p) for p in approved}) != len(approved)
            or any(p.startswith(d + '/') for p in approved for d in directories if p != d)):
        raise ValueError('Source allowlist is empty, ambiguous or redundant')
    if not isinstance(limits, Limits) or any(type(v) is not int or v <= 0 or v > getattr(Limits(), k)
           for k, v in vars(limits).items()) or set(vars(limits)) != set(vars(Limits())):
        raise ValueError('Limits may only tighten the archive bounds')
    if any(len(p.split('/')) + 1 > limits.path_depth for p in approved):
        raise ValueError('Approved source path exceeds depth bound')
    if path_semantics == 'portable':
        for name in (prefix,) + approved:
            _portable(name)
    ancestors = {p.rsplit('/', n)[0] for p in approved for n in range(1, p.count('/') + 1)}
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError('Source must be a regular local archive')
    with source.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        if not 0 < size <= limits.archive_bytes:
            raise ValueError('Archive byte limit exceeded')
        if _digest(handle) != expected_sha256:
            raise ValueError('Archive differs from its retained SHA256')
        count, central_start = _directory_bound(handle, size, limits)
        try:
            with zipfile.ZipFile(handle) as archive:
                entries = archive.infolist()
                if len(entries) != count:
                    raise ValueError('Archive entry count disagrees with its directory')
                if min(i.header_offset for i in entries) != 0:
                    raise ValueError('Archive has an unsupported executable or opaque prefix')
                seen, tree_files, tree_dirs, present = {}, [], set(), set()
                tree_paths, path_bytes, cursor = set(), 0, 0
                def tree_path(value):
                    nonlocal path_bytes
                    if value not in tree_paths:
                        path_bytes += len(value.encode('utf8'))
                        tree_paths.add(value)
                        if len(tree_paths) > limits.tree_nodes or path_bytes > limits.tree_path_bytes:
                            raise ValueError('Derived source tree exceeds bounds')
                total = 0
                for info in sorted(entries, key=lambda i: i.header_offset):
                    if info.orig_filename != info.filename:
                        raise ValueError('Archive name contains a truncated alias')
                    name = _path(info.filename[:-1] if info.is_dir() else info.filename)
                    if len(name.split('/')) > limits.path_depth:
                        raise ValueError('Archive path exceeds depth bound')
                    if path_semantics == 'portable':
                        _portable(name)
                    key = identity(name)
                    if key in seen:
                        raise ValueError('Duplicate or aliased archive entry')
                    seen[key] = info.is_dir()
                    if name == prefix:
                        if not info.is_dir():
                            raise ValueError('Archive wrapper is not a directory')
                        relative = ''
                    elif name.startswith(prefix + '/'):
                        relative = name[len(prefix) + 1:]
                    else:
                        raise ValueError('Archive entry is outside the approved wrapper')
                    mode = stat.S_IFMT(info.external_attr >> 16)
                    if (mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                            or mode == stat.S_IFDIR and not info.is_dir()
                            or mode == stat.S_IFREG and info.is_dir()
                            or info.external_attr & 0x10 and not info.is_dir()
                            or info.flag_bits & 1
                            or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                            or info.volume or info.extract_version > 20 or not 0 <= info.header_offset < central_start):
                        raise ValueError('Archive contains links, special files, encryption or unsupported encoding')
                    _extra(info.extra)
                    inside = any(relative == d or relative.startswith(d + '/') for d in directories)
                    if info.is_dir():
                        if info.file_size or (relative and not inside and relative not in ancestors):
                            raise ValueError('Unapproved or nonempty directory entry')
                        if relative in files:
                            raise ValueError('Approved file is a directory')
                        if relative:
                            tree_dirs.add(relative)
                    elif not relative or relative in directories or not (inside or relative in files):
                        raise ValueError('Unapproved file entry')
                    if info.file_size > limits.file_bytes or info.file_size > max(1, info.compress_size) * limits.compression_ratio:
                        raise ValueError('Archive member exceeds byte or expansion limits')
                    total += info.file_size
                    if total > limits.source_bytes:
                        raise ValueError('Source byte limit exceeded')
                    digest, read, cursor = _member(handle, info, cursor, central_start, limits)
                    if relative:
                        tree_path(relative)
                        present.update(p for p in approved if relative == p or p in directories and relative.startswith(p + '/'))
                        for n in range(1, relative.count('/') + 1):
                            parent = relative.rsplit('/', n)[0]
                            tree_path(parent)
                            tree_dirs.add(parent)
                        if not info.is_dir():
                            tree_files.append(dict(path=relative, bytes=read, sha256=digest))
                if cursor != central_start:
                    raise ValueError('Unindexed local archive data')
                # Catch a file used as another member's parent, including case aliases
                # when ZIPs omit explicit directory entries.
                for directory in tree_dirs:
                    full_key = identity(prefix + '/' + directory)
                    if full_key in seen and seen[full_key] is False:
                        raise ValueError('Archive file shadows a directory')
                canonical_dirs = {}
                for directory in tree_dirs:
                    key = identity(directory)
                    if key in canonical_dirs and canonical_dirs[key] != directory:
                        raise ValueError('Aliased implicit archive directory')
                    canonical_dirs[key] = directory
                if present != set(approved):
                    raise ValueError('An approved source item is missing')
                tree = dict(path_semantics=path_semantics, files=sorted(tree_files, key=lambda f: f['path']), directories=sorted(tree_dirs))
                tree_sha = hashlib.sha256(json.dumps(tree, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, UnicodeError, zlib.error):
            raise ValueError('Archive integrity validation failed') from None
        if _digest(handle) != expected_sha256:
            raise ValueError('Archive changed during validation')
    return dict(schema='inert-source-manifest/1', archive_sha256=expected_sha256,
                archive_bytes=size, entry_count=count, source_bytes=total,
                tree_node_count=len(tree_paths), tree_path_bytes=path_bytes,
                prefix=prefix, approved_directories=sorted(directories), approved_files=sorted(files),
                tree_sha256=tree_sha, **tree,
                limits='Exact archive bytes only. No extraction, execution, secret-clearance, live-source equivalence, activation inventory, approval or publishing certificate.')
