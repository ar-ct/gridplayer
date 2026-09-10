from pathlib import Path
from types import SimpleNamespace

import gridplayer.widgets.video_block as video_block


class _DummyVideoBlock:
    is_video_initialized = True
    is_local_file = True

    def __init__(self, uri: Path):
        self.video_params = SimpleNamespace(uri=uri)
        self._shuffle_directory_root = None
        self.switched_to = []

    def switch_video(self, path: Path):
        self.switched_to.append(path)
        self.video_params.uri = path


class _FakeSignal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _SetVideoDummy:
    def __init__(self, video_params, root: Path | None):
        self.video_params = video_params
        self._shuffle_directory_root = root
        self.load_video = _FakeSignal()
        self.size_tuple = (640, 360)
        self.url_resolver = SimpleNamespace(resolve=lambda *_args: None)
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1


def _local_video(uri: Path):
    return SimpleNamespace(uri=uri, is_local_file=True, is_http_url=False)


def test_shuffle_root_is_scoped_to_each_video_block(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    nested = collection / "nested"
    block_a = _DummyVideoBlock(collection / "a.mp4")
    block_b = _DummyVideoBlock(nested / "b.mp4")
    calls = []

    def fake_next(file, is_shuffle=False, root=None):
        calls.append((file, is_shuffle, root))
        if file == block_a.video_params.uri:
            return collection / "other" / "c.mp4"
        return nested / "d.mp4"

    monkeypatch.setattr(video_block, "next_video_file", fake_next)

    video_block.VideoBlock.shuffle_video(block_a)
    video_block.VideoBlock.shuffle_video(block_b)

    assert calls[0][1:] == (True, collection)
    assert calls[1][1:] == (True, nested)
    assert block_a._shuffle_directory_root == collection
    assert block_b._shuffle_directory_root == nested


def test_shuffle_keeps_its_root_across_nested_transitions(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    first = collection / "a.mp4"
    second = collection / "one" / "b.mp4"
    third = collection / "another" / "deep" / "c.mp4"
    block = _DummyVideoBlock(first)
    roots = []
    results = iter([second, third])

    def fake_next(file, is_shuffle=False, root=None):
        roots.append(root)
        return next(results)

    monkeypatch.setattr(video_block, "next_video_file", fake_next)

    video_block.VideoBlock.shuffle_video(block)
    video_block.VideoBlock.shuffle_video(block)

    assert roots == [collection, collection]
    assert block.video_params.uri == third


def test_normal_next_does_not_narrow_established_shuffle_root(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    nested = collection / "nested"
    current = nested / "b.mp4"
    sequential = nested / "c.mp4"
    random_pick = collection / "other" / "d.mp4"
    block = _DummyVideoBlock(current)
    block._shuffle_directory_root = collection
    shuffle_roots = []

    def fake_next(file, is_shuffle=False, root=None):
        if is_shuffle:
            shuffle_roots.append(root)
            return random_pick
        return sequential

    monkeypatch.setattr(video_block, "next_video_file", fake_next)

    video_block.VideoBlock.next_video(block)
    video_block.VideoBlock.shuffle_video(block)

    assert block.switched_to == [sequential, random_pick]
    assert shuffle_roots == [collection]
    assert block._shuffle_directory_root == collection


def test_normal_previous_does_not_narrow_established_shuffle_root(
    tmp_path, monkeypatch
):
    collection = tmp_path / "collection"
    nested = collection / "nested"
    current = nested / "c.mp4"
    sequential = nested / "b.mp4"
    random_pick = collection / "other" / "a.mp4"
    block = _DummyVideoBlock(current)
    block._shuffle_directory_root = collection
    shuffle_roots = []

    monkeypatch.setattr(video_block, "previous_video_file", lambda _file: sequential)

    def fake_next(file, is_shuffle=False, root=None):
        assert is_shuffle is True
        shuffle_roots.append(root)
        return random_pick

    monkeypatch.setattr(video_block, "next_video_file", fake_next)

    video_block.VideoBlock.previous_video(block)
    video_block.VideoBlock.shuffle_video(block)

    assert block.switched_to == [sequential, random_pick]
    assert shuffle_roots == [collection]
    assert block._shuffle_directory_root == collection


def test_set_video_preserves_shuffle_root_for_same_collection_reload(
    tmp_path, monkeypatch
):
    collection = tmp_path / "collection"
    nested_video = _local_video(collection / "nested" / "b.mp4")
    block = _SetVideoDummy(video_params=None, root=collection)

    monkeypatch.setattr(video_block, "get_vlc_options", lambda _video: [])

    video_block.VideoBlock.set_video(block, nested_video)

    assert block._shuffle_directory_root == collection
    assert block.video_params is nested_video
    assert block.reset_calls == 0
    assert len(block.load_video.calls) == 1


def test_set_video_clears_shuffle_root_when_leaving_collection(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    old_video = _local_video(collection / "nested" / "b.mp4")
    other_video = _local_video(tmp_path / "other_collection" / "x.mp4")
    block = _SetVideoDummy(video_params=old_video, root=collection)

    monkeypatch.setattr(video_block, "get_vlc_options", lambda _video: [])

    video_block.VideoBlock.set_video(block, other_video)

    assert block._shuffle_directory_root is None
    assert block.video_params is other_video
    assert block.reset_calls == 1
    assert len(block.load_video.calls) == 1


def test_set_video_clears_shuffle_root_for_non_local_source(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    old_video = _local_video(collection / "a.mp4")
    stream = SimpleNamespace(
        uri="https://example.invalid/video",
        is_local_file=False,
        is_http_url=True,
    )
    block = _SetVideoDummy(video_params=old_video, root=collection)

    monkeypatch.setattr(video_block, "get_vlc_options", lambda _video: [])

    video_block.VideoBlock.set_video(block, stream)

    assert block._shuffle_directory_root is None
    assert block.video_params is stream
    assert block.reset_calls == 1
    assert block.load_video.calls == []
