import os
import random
from dataclasses import dataclass
from pathlib import Path

from gridplayer.params.extensions import SUPPORTED_MEDIA_EXT


@dataclass(frozen=True)
class _DirectoryIndex:
    files: tuple[Path, ...]
    positions: dict[Path, int]
    directory_mtimes: tuple[tuple[Path, int], ...]


_INDEX_CACHE: dict[tuple[Path, bool], _DirectoryIndex] = {}
_RANDOM_ROOT_BY_FILE: dict[Path, Path] = {}


def next_video_file(
    file: Path, is_shuffle: bool = False, root: Path | None = None
) -> Path | None:
    """Return the next media file.

    Normal navigation keeps the original alphabetical, non-recursive behavior.
    Shuffle navigation includes supported media from all subdirectories below
    the collection root and remembers that root across successive random picks.
    """
    if is_shuffle:
        return random_video_file(file, recursive=True, root=root)

    index = _get_directory_index(file.parent, recursive=False)
    current_index = index.positions.get(file)
    if current_index is None or not index.files:
        return None

    return index.files[(current_index + 1) % len(index.files)]


def previous_video_file(file: Path) -> Path | None:
    index = _get_directory_index(file.parent, recursive=False)
    current_index = index.positions.get(file)
    if current_index is None or not index.files:
        return None

    return index.files[(current_index - 1) % len(index.files)]


def random_video_file(
    file: Path, recursive: bool = True, root: Path | None = None
) -> Path | None:
    """Return a random media file without immediately repeating *file*.

    For recursive navigation the first file's directory becomes the collection
    root. The selected file is associated with that root so the pool does not
    collapse to a nested subdirectory on the next random transition.
    """
    if root is None:
        collection_root = _RANDOM_ROOT_BY_FILE.get(file, file.parent)
    else:
        collection_root = root

    index = _get_directory_index(collection_root, recursive=recursive)
    file_count = len(index.files)
    if file_count == 0:
        return None

    current_index = index.positions.get(file)
    if current_index is None:
        selected = random.choice(index.files)
    elif file_count == 1:
        selected = index.files[0]
    else:
        # Pick from N-1 positions and skip the current one. This is O(1), avoids
        # copying/shuffling a potentially huge list, and guarantees no immediate
        # repeat when another file exists.
        random_index = random.randrange(file_count - 1)
        if random_index >= current_index:
            random_index += 1
        selected = index.files[random_index]

    if recursive:
        _RANDOM_ROOT_BY_FILE[file] = collection_root
        _RANDOM_ROOT_BY_FILE[selected] = collection_root

    return selected


def clear_directory_index_cache() -> None:
    """Clear cached navigation state (primarily useful for tests)."""
    _INDEX_CACHE.clear()
    _RANDOM_ROOT_BY_FILE.clear()


def _get_directory_index(root: Path, recursive: bool) -> _DirectoryIndex:
    root = root.absolute()
    cache_key = (root, recursive)
    cached = _INDEX_CACHE.get(cache_key)

    if cached is not None and _directory_index_is_current(cached):
        return cached

    index = _scan_directory(root, recursive)
    _INDEX_CACHE[cache_key] = index
    return index


def _directory_index_is_current(index: _DirectoryIndex) -> bool:
    """Validate a cached index by checking directory metadata only.

    Adding, removing or renaming a file/subdirectory updates its containing
    directory's mtime. Checking the comparatively small directory set avoids
    re-stat'ing and re-sorting thousands of media files on every navigation.
    """
    for directory, old_mtime_ns in index.directory_mtimes:
        try:
            if directory.stat().st_mtime_ns != old_mtime_ns:
                return False
        except OSError:
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
                    try:
                        if entry.is_file(follow_symlinks=False):
                            path = Path(entry.path)
                            if path.suffix[1:].lower() in SUPPORTED_MEDIA_EXT:
                                files.append(path)
                        elif recursive and entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                    except OSError:
                        continue
        except OSError:
            continue

        if not recursive:
            break

    files.sort()

    directory_mtimes: list[tuple[Path, int]] = []
    for directory in directories:
        try:
            directory_mtimes.append((directory, directory.stat().st_mtime_ns))
        except OSError:
            directory_mtimes.append((directory, 0))

    file_tuple = tuple(files)
    return _DirectoryIndex(
        files=file_tuple,
        positions={path: index for index, path in enumerate(file_tuple)},
        directory_mtimes=tuple(directory_mtimes),
    )
