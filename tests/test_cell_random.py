from PyQt5.QtGui import QKeySequence

from gridplayer.utils.cell_random import (
    CELL_RANDOM_SEEK_ACTION_IDS,
    CELL_RANDOM_SHORTCUT_KEYS,
    CellRandomController,
    release_digit_seek_shortcuts,
)


class FakeVideoBlock:
    def __init__(self, name):
        self.name = name
        self.shuffle_calls = 0

    def shuffle_video(self):
        self.shuffle_calls += 1


class FakeAction:
    def __init__(self, *shortcuts):
        self._shortcuts = [QKeySequence(shortcut) for shortcut in shortcuts]

    def shortcuts(self):
        return list(self._shortcuts)

    def setShortcuts(self, shortcuts):
        self._shortcuts = list(shortcuts)


def shortcut_texts(action):
    return [shortcut.toString(QKeySequence.PortableText) for shortcut in action.shortcuts()]


def test_digit_shortcuts_cover_cells_one_through_nine():
    assert CELL_RANDOM_SHORTCUT_KEYS == tuple(str(number) for number in range(1, 10))
    assert CELL_RANDOM_SEEK_ACTION_IDS == tuple(
        f"{number}0%" for number in range(1, 10)
    )


def test_shuffle_cell_targets_only_requested_grid_position():
    blocks = [FakeVideoBlock(str(number)) for number in range(1, 5)]
    controller = CellRandomController(lambda: blocks)

    assert controller.shuffle_cell(3) is True
    assert [block.shuffle_calls for block in blocks] == [0, 0, 1, 0]


def test_shuffle_cell_tracks_current_grid_order():
    first = FakeVideoBlock("first")
    second = FakeVideoBlock("second")
    blocks = [first, second]
    controller = CellRandomController(lambda: blocks)

    controller.shuffle_cell(1)
    blocks[:] = [second, first]
    controller.shuffle_cell(1)

    assert first.shuffle_calls == 1
    assert second.shuffle_calls == 1


def test_shuffle_missing_cell_is_safe_no_op():
    block = FakeVideoBlock("only")
    controller = CellRandomController(lambda: [block])

    assert controller.shuffle_cell(0) is False
    assert controller.shuffle_cell(2) is False
    assert block.shuffle_calls == 0


def test_release_digit_seek_shortcuts_removes_only_bare_digits():
    actions = {
        action_id: FakeAction(digit, f"Ctrl+{digit}")
        for digit, action_id in zip(
            CELL_RANDOM_SHORTCUT_KEYS, CELL_RANDOM_SEEK_ACTION_IDS, strict=True
        )
    }

    release_digit_seek_shortcuts(actions)

    for digit, action_id in zip(
        CELL_RANDOM_SHORTCUT_KEYS, CELL_RANDOM_SEEK_ACTION_IDS, strict=True
    ):
        assert shortcut_texts(actions[action_id]) == [f"Ctrl+{digit}"]


def test_release_digit_seek_shortcuts_tolerates_missing_actions():
    action = FakeAction("1")
    actions = {"10%": action}

    release_digit_seek_shortcuts(actions)

    assert shortcut_texts(action) == []
