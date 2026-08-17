import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from gridplayer.params.extensions import SUPPORTED_MEDIA_EXT


@dataclass(frozen=True)
class _DirectoryIndex:
    files: tuple[Path, ...]
    positions: dict[Path, int]
    directory_mtimes: tuple[tuple[Path, int], ...]


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

    ``root`` defines the collection boundary for recursive navigation.  The
    caller is responsible for preserving that root across successive random
    transitions.  ``secrets.randbelow`` uses the operating system's
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

    # Draw uniformly from N-1 slots and skip the current one.  Each other file
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
    _INDEX_CACHE[cache_key] = index
    return index


def _safe_mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _entry_flags(entry) -> tuple[bool, bool]:
    try:
        return entry.is_file(follow_symlinks=False), entry.is_dir(follow_symlinks=False)
    except OSError:
        return False, False


def _directory_index_is_current(index: _DirectoryIndex) -> bool:
    """Validate a cached index by checking directory metadata only.

    Adding, removing or renaming a file/subdirectory updates its containing
    directory's mtime. Checking the comparatively small directory set avoids
    re-stat'ing and re-sorting thousands of media files on every navigation.
    """
    for directory, old_mtime_ns in index.directory_mtimes:
        if _safe_mtime_ns(directory) != old_mtime_ns:
            return False

    return True


def _scan_directory(root: Path, recursive: bool) -> _DirectoryIndex:
    files: list[Path] = []
    directories: list[Path] = []
    pending = [root]

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
            continue

        if not recursive:
            break

    files.sort()

    directory_mtimes = [
        (directory, _safe_mtime_ns(directory) or 0) for directory in directories
    ]

    file_tuple = tuple(files)
    return _DirectoryIndex(
        files=file_tuple,
        positions={path: index for index, path in enumerate(file_tuple)},
        directory_mtimes=tuple(directory_mtimes),
    )
