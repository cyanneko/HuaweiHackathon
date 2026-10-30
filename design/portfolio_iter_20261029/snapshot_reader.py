"""Read frozen report JSON without unpacking measurement archives.

Real files have priority. Only *_summary.json directly under this module's
PORT directory may fall back to *_measurements.zip in that same directory.
Matching uses the exact entry basename, never a suffix/substring match. Every
copy found must have identical bytes, including a real file if one exists.
All operations are read-only; no archive is extracted or modified.
"""
from functools import lru_cache
import json
from pathlib import Path, PurePosixPath
import zipfile


PORT = Path(__file__).resolve().parent


def _eligible(path):
    return path.parent == PORT and path.name.endswith('_summary.json')


def _signature(path):
    info = path.stat()
    return str(path), info.st_size, info.st_mtime_ns


@lru_cache(maxsize=128)
def _archive_index(archive_name, size, modified_ns):
    """Cache central-directory positions, invalidated by size/mtime changes."""
    del size, modified_ns
    names = {}
    with zipfile.ZipFile(archive_name, 'r') as archive:
        for position, info in enumerate(archive.infolist()):
            if info.is_dir():
                continue
            basename = PurePosixPath(info.filename.replace('\\', '/')).name
            names.setdefault(basename, []).append(position)
    return {name: tuple(positions) for name, positions in names.items()}


@lru_cache(maxsize=8)
def _archive_entry(archive_name, size, modified_ns, position):
    del size, modified_ns
    with zipfile.ZipFile(archive_name, 'r') as archive:
        # ZipInfo, rather than a name lookup, preserves duplicate entries so
        # even duplicate basenames within one ZIP are checked independently.
        info = archive.infolist()[position]
        return info.filename, archive.read(info)


def _summary_bytes(path):
    """Return preferred bytes or None; reject any conflicting frozen copy."""
    preferred = path.read_bytes() if path.is_file() else None
    preferred_origin = str(path) if preferred is not None else None
    for archive_path in sorted(PORT.glob('*_measurements.zip')):
        if not archive_path.is_file():
            continue
        signature = _signature(archive_path)
        positions = _archive_index(*signature).get(path.name, ())
        for position in positions:
            member_name, body = _archive_entry(*signature, position)
            origin = archive_path.name + '!' + member_name
            if preferred is None:
                preferred, preferred_origin = body, origin
            elif body != preferred:
                raise ValueError('Conflicting frozen summary bytes for '
                    + path.name + ': ' + str(preferred_origin) + ' differs from ' + origin)
        if _signature(archive_path) != signature:
            raise RuntimeError('Measurement archive changed during read: ' + archive_path.name)
    return preferred


def available(path):
    """Whether an exact JSON source exists; conflicts/corrupt ZIPs still raise."""
    path = Path(path).resolve()
    if not _eligible(path):
        return path.is_file()
    return _summary_bytes(path) is not None


def read_json(path):
    """Read a real JSON file or the byte-identical frozen summary ZIP member."""
    path = Path(path).resolve()
    if not _eligible(path):
        # Models, catalog, window bounds, nested diagnostics and all other JSON
        # retain direct filesystem semantics. No general-purpose ZIP fallback.
        return json.loads(path.read_text(encoding='utf8'))
    body = _summary_bytes(path)
    if body is None:
        raise FileNotFoundError('No real file or frozen measurement member for ' + str(path))
    return json.loads(body.decode('utf8'))
