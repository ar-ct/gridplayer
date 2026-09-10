import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from gridplayer.params.extensions import SUPPORTED_MEDIA_EXT

# Directory mtimes normally invalidate the cache immediately. Windows filesystems
# can defer directory timestamp updates, so force a bounded periodic rescan as a
# correctness fallback without paying the cost on every navigation action.
_INDEX_MAX_AGE_NS = 60 * 1_000_000_000


@dataclass(frozen=True)
class _DirectoryIndex:
    files: tuple[Path, ...]
    positions: dict[Path, int]
    directory_mtimes: tuple[tuple[Path, int], ...]
    built_at_ns: int
    is_complete: bool


_INDEX_CACHE: dict[tuple[Path, bool], _DirectoryIndex] = {}


def next_video_file(
    file: Path, is_shuffle: bool = False, root: Path | None = None
) -> Path | None:
    """Return the next media file.

    Normal navigation keeps the original alphabetical, non-recursive behavior.
    Shuffle navigation includes supported media from all subdirectories below
    the explicit collection root.
    """
    file = file.absolute()

    if is_shuffle:
        return random_video_file(file, recursive=True, root=root)

    index = _get_directory_index(file.parent, recursive=False)
    current_index = index.positions.get(file)
    if current_index is None or not index.files:
        return None

    return index.files[(current_index + 1) % len(index.files)]


def previous_video_file(file: Path) -> Path | None:
    file = file.absolute()
    index = _get_directory_index(file.parent, recursive=False)
    current_index = index.positions.get(file)
    if current_index is None or not index.files:
        return None

    return index.files[(current_index - 1) % len(index.files)]


def random_video_file(
    file: Path, recursive: bool = True, root: Path | None = None
) -> Path | None:
    """Return a uniformly selected media file other than *file* when possible.

    ``root`` defines the collection boundary for recursive navigation. The
    caller is responsible for preserving that root across successive random
    transitions. ``secrets.randbelow`` uses the operating system's
    cryptographically strong random source and introduces no modulo bias.
    """
    file = file.absolute()
    collection_root = (root if root is not None else file.parent).absolute()

    index = _get_directory_index(collection_root, recursive=recursive)
    file_count = len(index.files)
    if file_count == 0:
        return None

    current_index = index.positions.get(file)
    if current_index is None:
        return index.files[secrets.randbelow(file_count)]
    if file_count == 1:
        return index.files[0]

    # Draw uniformly from N-1 slots and skip the current one. Each other file
    # therefore has exactly 1/(N-1) probability, regardless of name, directory,
    # sort position or nesting depth.
    random_index = secrets.randbelow(file_count - 1)
    if random_index >= current_index:
        random_index += 1

    return index.files[random_index]


def clear_directory_index_cache() -> None:
    """Clear cached directory indexes (primarily useful for tests)."""
    _INDEX_CACHE.clear()


def _get_directory_index(root: Path, recursive: bool) -> _DirectoryIndex:
    root = root.absolute()
    cache_key = (root, recursive)
    cached = _INDEX_CACHE.get(cache_key)

    if cached is not None and _directory_index_is_current(cached):
        return cached

    index = _scan_directory(root, recursive)

    # A transient filesystem error must never poison the cache with a partial
    # directory tree. Preserve a previous complete snapshot when available and
    # retry the scan on the next navigation action.
    if index.is_complete:
        _INDEX_CACHE[cache_key] = index
        return index

    if cached is not None:
        return cached

    # On the first scan there is no last-known-good snapshot. The partial result
    # can still make the current action useful, but it deliberately remains
    # uncached so the very next action retries the full traversal.
    return index


def _safe_mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _entry_flags(entry) -> tuple[bool, bool]:
    # Let OSError propagate to _scan_directory so a failed DirEntry metadata
    # query marks the entire traversal incomplete instead of silently dropping
    # one branch and caching the truncated result.
    return entry.is_file(follow_symlinks=False), entry.is_dir(follow_symlinks=False)


def _directory_index_is_current(index: _DirectoryIndex) -> bool:
    """Validate a cached index using metadata plus a bounded refresh fallback."""
    if not index.is_complete:
        return False

    if time.monotonic_ns() - index.built_at_ns >= _INDEX_MAX_AGE_NS:
        return False

    for directory, old_mtime_ns in index.directory_mtimes:
        if _safe_mtime_ns(directory) != old_mtime_ns:
            return False

    return True


def _scan_directory(root: Path, recursive: bool) -> _DirectoryIndex:
    files: list[Path] = []
    directories: list[Path] = []
    pending = [root]
    is_complete = True

    while pending:
        directory = pending.pop()
        directories.append(directory)

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    is_file, is_dir = _entry_flags(entry)
                    if is_file:
                        path = Path(entry.path)
                        if path.suffix[1:].lower() in SUPPORTED_MEDIA_EXT:
                            files.append(path)
                    elif recursive and is_dir:
                        pending.append(Path(entry.path))
        except OSError:
            # Keep traversing directories that were already discovered, but do
            # not allow this partial result to become a trusted cache entry.
            is_complete = False

        if not recursive:
            break

    files.sort()

    directory_mtimes = []
    for directory in directories:
        mtime_ns = _safe_mtime_ns(directory)
        if mtime_ns is None:
            is_complete = False
            mtime_ns = 0
        directory_mtimes.append((directory, mtime_ns))

    file_tuple = tuple(files)
    return _DirectoryIndex(
        files=file_tuple,
        positions={path: index for index, path in enumerate(file_tuple)},
        directory_mtimes=tuple(directory_mtimes),
        built_at_ns=time.monotonic_ns(),
        is_complete=is_complete,
    )
