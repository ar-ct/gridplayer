from types import SimpleNamespace

from gridplayer.player.player import Player
from gridplayer.utils.keymap import default_keymap


def test_end_and_home_are_unused_by_default_keymap():
    assigned = {
        shortcut
        for shortcuts in default_keymap().values()
        for shortcut in shortcuts
    }

    assert "End" not in assigned
    assert "Home" not in assigned


def test_shuffle_all_videos_calls_each_block_once():
    class FakeVideoBlock:
        def __init__(self):
            self.shuffle_calls = 0

        def shuffle_video(self):
            self.shuffle_calls += 1

    blocks = [FakeVideoBlock() for _ in range(4)]
    fake_player = SimpleNamespace(
        _context=SimpleNamespace(video_blocks=blocks),
    )

    Player._shuffle_all_videos(fake_player)

    assert [block.shuffle_calls for block in blocks] == [1, 1, 1, 1]


def test_shuffle_all_videos_handles_empty_grid():
    fake_player = SimpleNamespace(
        _context=SimpleNamespace(video_blocks=[]),
    )

    Player._shuffle_all_videos(fake_player)
