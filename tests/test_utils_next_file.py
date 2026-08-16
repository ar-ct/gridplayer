from pathlib import Path

import gridplayer.utils.next_file as next_file


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def setup_function():
    next_file.clear_directory_index_cache()


def test_next_and_previous_keep_original_non_recursive_order(tmp_path):
    a = _touch(tmp_path / "a.mp4")
    b = _touch(tmp_path / "b.mp4")
    _touch(tmp_path / "nested" / "c.mp4")

    assert next_file.next_video_file(a) == b
    assert next_file.next_video_file(b) == a
    assert next_file.previous_video_file(a) == b


def test_shuffle_uses_subdirectories_and_never_immediately_repeats(tmp_path, monkeypatch):
    current = _touch(tmp_path / "a.mp4")
    nested = _touch(tmp_path / "one" / "b.mp4")
    deep = _touch(tmp_path / "two" / "deep" / "c.mp4")
    _touch(tmp_path / "two" / "ignored.txt")

    monkeypatch.setattr(next_file.random, "randrange", lambda n: 0)
    assert next_file.next_video_file(current, is_shuffle=True) in {nested, deep}


def test_cached_index_is_reused_until_directory_changes(tmp_path, monkeypatch):
    a = _touch(tmp_path / "a.mp4")
    _touch(tmp_path / "b.mp4")

    real_scan = next_file._scan_directory
    calls = 0

    def counted_scan(root, recursive):
        nonlocal calls
        calls += 1
        return real_scan(root, recursive)

    monkeypatch.setattr(next_file, "_scan_directory", counted_scan)

    next_file.next_video_file(a)
    next_file.next_video_file(a)
    assert calls == 1

    _touch(tmp_path / "c.mp4")
    next_file.next_video_file(a)
    assert calls == 2


def test_recursive_cache_detects_changes_in_nested_directory(tmp_path, monkeypatch):
    current = _touch(tmp_path / "a.mp4")
    nested_dir = tmp_path / "nested"
    _touch(nested_dir / "b.mp4")

    real_scan = next_file._scan_directory
    calls = 0

    def counted_scan(root, recursive):
        nonlocal calls
        calls += 1
        return real_scan(root, recursive)

    monkeypatch.setattr(next_file, "_scan_directory", counted_scan)
    monkeypatch.setattr(next_file.random, "randrange", lambda n: 0)

    next_file.random_video_file(current, recursive=True)
    next_file.random_video_file(current, recursive=True)
    assert calls == 1

    _touch(nested_dir / "c.mp4")
    next_file.random_video_file(current, recursive=True)
    assert calls == 2
