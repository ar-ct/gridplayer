from PyQt5.QtGui import QKeySequence

CELL_RANDOM_SHORTCUT_KEYS = tuple(str(number) for number in range(1, 10))
CELL_RANDOM_SEEK_ACTION_IDS = tuple(f"{number}0%" for number in range(1, 10))


class CellRandomController:
    """Route a numbered shortcut to the matching video block in grid order."""

    def __init__(self, video_blocks_provider):
        self._video_blocks_provider = video_blocks_provider

    def shuffle_cell(self, cell_number: int) -> bool:
        if cell_number < 1:
            return False

        video_blocks = self._video_blocks_provider()
        index = cell_number - 1
        if index >= len(video_blocks):
            return False

        video_blocks[index].shuffle_video()
        return True


def release_digit_seek_shortcuts(actions) -> None:
    """Free bare 1-9 keys while preserving any other bindings on seek actions."""

    for digit, action_id in zip(
        CELL_RANDOM_SHORTCUT_KEYS, CELL_RANDOM_SEEK_ACTION_IDS, strict=True
    ):
        action = actions.get(action_id)
        if action is None:
            continue

        shortcuts = [
            shortcut
            for shortcut in action.shortcuts()
            if shortcut.toString(QKeySequence.PortableText) != digit
        ]
        action.setShortcuts(shortcuts)
