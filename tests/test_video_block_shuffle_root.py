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


def test_normal_next_resets_shuffle_collection_root(tmp_path, monkeypatch):
    collection = tmp_path / "collection"
    current = collection / "nested" / "b.mp4"
    block = _DummyVideoBlock(current)
    block._shuffle_directory_root = collection

    monkeypatch.setattr(
        video_block,
        "next_video_file",
        lambda file, is_shuffle=False, root=None: current.parent / "c.mp4",
    )

    video_block.VideoBlock.next_video(block)

    assert block._shuffle_directory_root is None
