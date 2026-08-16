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


def next_video_file(file: Path, is_shuffle: bool = False) -> Path | None:
    """Return the next media file.

    Normal navigation keeps the original alphabetical, non-recursive behavior.
    Shuffle navigation uses the current directory as the collection root and
    includes supported media from all of its subdirectories.
    """
    if is_shuffle:
        return random_video_file(file, recursive=True)

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


def random_video_file(file: Path, recursive: bool = True) -> Path | None:
    """Return a random media file without immediately repeating *file*.

    With ``recursive=True`` the current file's directory is treated as the
    collection root and all supported media below it are eligible.
    """
    index = _get_directory_index(file.parent, recursive=recursive)
    file_count = len(index.files)
    if file_count == 0:
        return None

    current_index = index.positions.get(file)
    if current_index is None:
        return random.choice(index.files)
    if file_count == 1:
        return index.files[0]

    # Pick from N-1 positions and skip the current one. This is O(1), avoids
    # copying/shuffling a potentially huge list, and guarantees no immediate
    # repeat when another file exists.
    random_index = random.randrange(file_count - 1)
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
                        # Preserve the old best-effort behavior when individual
                        # filesystem entries cannot be inspected.
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
            # A disappearing directory makes the just-built cache immediately
            # stale, so a zero sentinel forces validation to fail next time.
            directory_mtimes.append((directory, 0))

    file_tuple = tuple(files)
    return _DirectoryIndex(
        files=file_tuple,
        positions={path: index for index, path in enumerate(file_tuple)},
        directory_mtimes=tuple(directory_mtimes),
    )
