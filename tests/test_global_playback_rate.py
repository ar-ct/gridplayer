from types import SimpleNamespace

from gridplayer.params.actions import ACTIONS
from gridplayer.player import player as player_module


class DummyVideoBlock:
    def __init__(self, block_id, *, rate=1.0, initialized=True, is_live=False):
        self.id = block_id
        self.video_params = SimpleNamespace(rate=rate)
        self.is_video_initialized = initialized
        self.is_live = is_live
        self.set_rate_calls = []

    def set_rate(self, rate):
        if self.is_live:
            return
        self.video_params.rate = rate
        self.set_rate_calls.append(rate)


def make_dummy_player(
    blocks=(), *, percent=player_module.GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT
):
    return SimpleNamespace(
        _global_playback_rate_percent=percent,
        _global_rate_known_block_ids=set(),
        _context=SimpleNamespace(video_blocks=list(blocks)),
    )


def default_action_keys():
    keys = set()
    for action in ACTIONS.values():
        if "key" in action:
            keys.add(action["key"])
        keys.update(action.get("keys", ()))
    return keys


def test_requested_global_rate_hotkeys_are_unused_by_default_actions():
    keys = default_action_keys()
    assert player_module.GLOBAL_PLAYBACK_RATE_INCREASE_KEY not in keys
    assert player_module.GLOBAL_PLAYBACK_RATE_DECREASE_KEY not in keys
    assert player_module.GLOBAL_PLAYBACK_RATE_RESET_KEY not in keys


def test_global_rate_is_applied_to_all_loaded_and_loading_blocks():
    loaded = DummyVideoBlock("loaded")
    loading = DummyVideoBlock("loading", initialized=False)
    player = make_dummy_player((loaded, loading))

    player_module.Player._set_global_playback_rate_percent(player, 130)

    assert player._global_playback_rate_percent == 130
    assert loaded.video_params.rate == 1.3
    assert loaded.set_rate_calls == [1.3]
    assert loading.video_params.rate == 1.3
    assert loading.set_rate_calls == []


def test_global_rate_clamps_to_50_through_200_percent():
    block = DummyVideoBlock("block")
    player = make_dummy_player((block,))

    player_module.Player._set_global_playback_rate_percent(player, 10)
    assert (
        player._global_playback_rate_percent
        == player_module.GLOBAL_PLAYBACK_RATE_MIN_PERCENT
    )
    assert block.video_params.rate == 0.5

    player_module.Player._set_global_playback_rate_percent(player, 999)
    assert (
        player._global_playback_rate_percent
        == player_module.GLOBAL_PLAYBACK_RATE_MAX_PERCENT
    )
    assert block.video_params.rate == 2.0


def test_global_rate_changes_in_exact_ten_percent_steps_and_resets():
    block = DummyVideoBlock("block")
    player = make_dummy_player((block,))

    player_module.Player._increase_global_playback_rate(player)
    assert player._global_playback_rate_percent == 110
    assert block.video_params.rate == 1.1

    player_module.Player._decrease_global_playback_rate(player)
    assert player._global_playback_rate_percent == 100
    assert block.video_params.rate == 1.0

    player_module.Player._set_global_playback_rate_percent(player, 170)
    player_module.Player._reset_global_playback_rate(player)
    assert (
        player._global_playback_rate_percent
        == player_module.GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT
    )
    assert block.video_params.rate == 1.0


def test_new_blocks_inherit_current_runtime_rate_without_resetting_old_blocks():
    old = DummyVideoBlock("old", rate=1.6)
    new = DummyVideoBlock("new", rate=1.0)
    player = make_dummy_player((old, new), percent=140)
    player._global_rate_known_block_ids = {"old"}

    player_module.Player._apply_global_rate_to_new_blocks(player)

    assert old.video_params.rate == 1.6
    assert old.set_rate_calls == []
    assert new.video_params.rate == 1.4
    assert new.set_rate_calls == [1.4]
    assert player._global_rate_known_block_ids == {"old", "new"}


def test_fresh_runtime_forces_new_blocks_back_to_100_percent():
    # Simulate a Video object carrying a previously saved non-default rate.
    block = DummyVideoBlock("new-run", rate=1.8)
    player = make_dummy_player((block,))

    player_module.Player._apply_global_rate_to_new_blocks(player)

    assert player._global_playback_rate_percent == 100
    assert block.video_params.rate == 1.0
    assert block.set_rate_calls == [1.0]
