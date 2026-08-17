import os
from pathlib import Path

import gridplayer.utils.next_file as next_file
from gridplayer.params.extensions import SUPPORTED_MEDIA_EXT


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path.absolute()


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

    monkeypatch.setattr(next_file.secrets, "randbelow", lambda n: 0)
    assert next_file.next_video_file(current, is_shuffle=True, root=tmp_path) in {
        nested,
        deep,
    }


def test_recursive_shuffle_keeps_explicit_original_root_after_nested_pick(
    tmp_path, monkeypatch
):
    root_file = _touch(tmp_path / "a.mp4")
    nested_file = _touch(tmp_path / "nested" / "b.mp4")
    other_branch = _touch(tmp_path / "other" / "c.mp4")

    picks = iter([0, 1])
    monkeypatch.setattr(next_file.secrets, "randbelow", lambda n: next(picks))

    first = next_file.next_video_file(root_file, is_shuffle=True, root=tmp_path)
    assert first == nested_file

    second = next_file.next_video_file(first, is_shuffle=True, root=tmp_path)
    assert second == other_branch


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
    monkeypatch.setattr(next_file.secrets, "randbelow", lambda n: 0)

    next_file.random_video_file(current, recursive=True, root=tmp_path)
    next_file.random_video_file(current, recursive=True, root=tmp_path)
    assert calls == 1

    _touch(nested_dir / "c.mp4")
    next_file.random_video_file(current, recursive=True, root=tmp_path)
    assert calls == 2


def test_recursive_index_contains_every_supported_extension(tmp_path):
    expected = set()
    for index, extension in enumerate(sorted(SUPPORTED_MEDIA_EXT)):
        expected.add(
            _touch(
                tmp_path
                / f"level_{index % 7}"
                / f"nested_{index % 13}"
                / f"media_{index}.{extension.upper()}"
            )
        )

    _touch(tmp_path / "not_media.txt")
    _touch(tmp_path / "nested" / "also_not_media.bin")

    index = next_file._get_directory_index(tmp_path, recursive=True)

    assert len(index.files) == len(expected)
    assert set(index.files) == expected
    assert len(index.positions) == len(expected)


def test_large_recursive_tree_does_not_truncate_file_count(tmp_path):
    # Exercise a genuinely large on-disk collection. There is deliberately no
    # scanner-side maximum; every supported file returned by os.scandir must be
    # retained. Keep the fixture large enough to expose accidental caps while
    # still being practical on CI Windows filesystems.
    file_count = 12_000
    directory_count = 60
    expected = set()

    for index in range(file_count):
        directory = tmp_path / f"group_{index % directory_count:02d}"
        expected.add(_touch(directory / f"clip_{index:05d}.mp4"))

    index = next_file._get_directory_index(tmp_path, recursive=True)

    assert len(index.files) == file_count
    assert len(index.positions) == file_count
    assert set(index.files) == expected


def test_unicode_long_and_windows_safe_special_names_are_not_lost(tmp_path):
    # Keep every individual component within both Windows' character limit and
    # POSIX's 255-byte component limit. The combined path remains intentionally
    # much longer than the traditional Windows MAX_PATH value of 260 chars.
    long_dir_1 = "Папка_" + "Ж" * 70
    long_dir_2 = "Mixed_кириллица_Latin_" + "я" * 65
    long_name = (
        "Видео 🎬 [2026] # & + = ! @ $ , ; ' ( ) [ ] { } _ "
        + "LongName_" * 16
        + "ЖЁаб.MP4"
    )

    special = _touch(tmp_path / long_dir_1 / long_dir_2 / long_name)
    mixed = _touch(
        tmp_path
        / "Обычная папка с пробелами"
        / "Latin-Кириллица_ёЁ №42 (final) [x] #1 & + = ! @ $.mKv"
    )

    index = next_file._get_directory_index(tmp_path, recursive=True)

    assert special in index.files
    assert mixed in index.files
    assert special in index.positions
    assert mixed in index.positions


def test_random_slot_mapping_is_exactly_uniform_over_all_other_files(
    tmp_path, monkeypatch
):
    files = [_touch(tmp_path / f"clip_{index:03d}.mp4") for index in range(101)]
    current = files[50]
    eligible = set(files) - {current}
    selected = []

    # Exhaust every possible raw output from randbelow(N-1). The skip-current
    # transform must map those N-1 equally likely integers one-to-one onto every
    # other file. This proves that sort position/name/depth cannot bias a pick.
    for raw_slot in range(len(files) - 1):
        monkeypatch.setattr(
            next_file.secrets,
            "randbelow",
            lambda n, raw_slot=raw_slot: raw_slot,
        )
        selected.append(
            next_file.random_video_file(current, recursive=True, root=tmp_path)
        )

    assert len(selected) == len(eligible)
    assert len(set(selected)) == len(eligible)
    assert set(selected) == eligible


def test_relative_input_path_is_normalized_before_lookup(tmp_path, monkeypatch):
    current = _touch(tmp_path / "a.mp4")
    other = _touch(tmp_path / "nested" / "b.mp4")
    monkeypatch.setattr(next_file.secrets, "randbelow", lambda n: 0)

    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert next_file.random_video_file(Path("a.mp4"), root=Path(".")) == other
        assert next_file.next_video_file(Path("a.mp4")) == current
    finally:
        os.chdir(old_cwd)
