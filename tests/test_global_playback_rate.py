from types import SimpleNamespace

from gridplayer.params.actions import ACTIONS
from gridplayer.utils import playback_rate


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


def make_controller(blocks=()):
    current_blocks = list(blocks)
    return playback_rate.GlobalPlaybackRateController(lambda: current_blocks), current_blocks


def default_action_keys():
    keys = set()
    for action in ACTIONS.values():
        if "key" in action:
            keys.add(action["key"])
        keys.update(action.get("keys", ()))
    return keys


def test_requested_global_rate_hotkeys_are_unused_by_default_actions():
    keys = default_action_keys()
    assert playback_rate.GLOBAL_PLAYBACK_RATE_INCREASE_KEY not in keys
    assert playback_rate.GLOBAL_PLAYBACK_RATE_DECREASE_KEY not in keys
    assert playback_rate.GLOBAL_PLAYBACK_RATE_RESET_KEY not in keys


def test_global_rate_defaults_to_100_percent():
    controller, _ = make_controller()

    assert controller.percent == playback_rate.GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT
    assert controller.rate == 1.0


def test_global_rate_is_applied_to_all_loaded_and_loading_blocks():
    loaded = DummyVideoBlock("loaded")
    loading = DummyVideoBlock("loading", initialized=False)
    controller, _ = make_controller((loaded, loading))

    controller.set_percent(130)

    assert controller.percent == 130
    assert controller.rate == 1.3
    assert loaded.video_params.rate == 1.3
    assert loaded.set_rate_calls == [1.3]
    assert loading.video_params.rate == 1.3
    assert loading.set_rate_calls == []


def test_global_rate_clamps_to_50_through_200_percent():
    block = DummyVideoBlock("block")
    controller, _ = make_controller((block,))

    controller.set_percent(10)
    assert controller.percent == playback_rate.GLOBAL_PLAYBACK_RATE_MIN_PERCENT
    assert controller.rate == 0.5
    assert block.video_params.rate == 0.5

    controller.set_percent(999)
    assert controller.percent == playback_rate.GLOBAL_PLAYBACK_RATE_MAX_PERCENT
    assert controller.rate == 2.0
    assert block.video_params.rate == 2.0


def test_global_rate_changes_in_exact_ten_percent_steps_and_resets():
    block = DummyVideoBlock("block")
    controller, _ = make_controller((block,))

    controller.increase()
    assert controller.percent == 110
    assert block.video_params.rate == 1.1

    controller.decrease()
    assert controller.percent == 100
    assert block.video_params.rate == 1.0

    controller.set_percent(170)
    controller.reset()
    assert controller.percent == playback_rate.GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT
    assert block.video_params.rate == 1.0


def test_repeated_steps_stop_exactly_at_requested_limits():
    block = DummyVideoBlock("block")
    controller, _ = make_controller((block,))

    for _ in range(20):
        controller.decrease()
    assert controller.percent == 50
    assert block.video_params.rate == 0.5

    for _ in range(30):
        controller.increase()
    assert controller.percent == 200
    assert block.video_params.rate == 2.0


def test_new_blocks_inherit_current_runtime_rate_without_resetting_old_blocks():
    old = DummyVideoBlock("old", rate=1.0)
    controller, blocks = make_controller((old,))
    controller.set_percent(140)

    # Simulate the existing single-cell C/X/Z controls changing only this cell.
    old.video_params.rate = 1.6
    old.set_rate_calls.clear()

    new = DummyVideoBlock("new", rate=1.0)
    blocks.append(new)
    controller.apply_to_new_blocks()

    assert old.video_params.rate == 1.6
    assert old.set_rate_calls == []
    assert new.video_params.rate == 1.4
    assert new.set_rate_calls == [1.4]


def test_fresh_runtime_forces_new_blocks_back_to_100_percent():
    # Simulate a Video object carrying a previously saved non-default rate.
    block = DummyVideoBlock("new-run", rate=1.8)
    controller, _ = make_controller((block,))

    controller.apply_to_new_blocks()

    assert controller.percent == 100
    assert block.video_params.rate == 1.0
    assert block.set_rate_calls == [1.0]


def test_live_video_model_tracks_global_rate_without_forcing_driver_rate():
    live = DummyVideoBlock("live", rate=1.0, is_live=True)
    controller, _ = make_controller((live,))

    controller.set_percent(150)

    assert live.video_params.rate == 1.5
    assert live.set_rate_calls == []
