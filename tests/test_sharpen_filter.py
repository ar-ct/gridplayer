from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

from gridplayer.dialogs.settings import SettingsDialog
from gridplayer.dialogs.settings_sharpen import (
    SHARPEN_DEFAULT_STRENGTH,
    SHARPEN_SETTING,
    SHARPEN_STEP,
    SHARPEN_UI_MAX,
    SharpenControl,
    attach_sharpen_control,
)
from gridplayer.params.static import VideoTransform
from gridplayer.player.managers import settings as settings_manager_module
from gridplayer.player.managers.settings import SettingsManager
from gridplayer.player.managers.video_blocks import VideoBlocksManager
from gridplayer.utils import libvlc_options_parser
from gridplayer.vlc_player.player_base import VlcPlayerBase
from gridplayer.vlc_player.static import MediaInput


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clear_sharpen_preview():
    libvlc_options_parser.set_sharpen_preview(None)
    yield
    libvlc_options_parser.set_sharpen_preview(None)


class _FakeSettings:
    def __init__(self, sigma):
        self.sigma = sigma

    def get(self, setting):
        assert setting == SHARPEN_SETTING
        return self.sigma


class _FakeSignal:
    def __init__(self):
        self.calls = 0

    def emit(self):
        self.calls += 1


class _FakeLog:
    def debug(self, *_args):
        pass


def _vlc_options(monkeypatch, sigma, transform=VideoTransform.NONE):
    monkeypatch.setattr(
        libvlc_options_parser, "Settings", lambda: _FakeSettings(sigma)
    )
    video = SimpleNamespace(transform=transform)
    return libvlc_options_parser.get_vlc_options(video)


def test_sharpen_is_absent_when_disabled(monkeypatch):
    assert _vlc_options(monkeypatch, 0.0) == []


def test_sharpen_uses_single_video_filter_chain(monkeypatch):
    options = _vlc_options(monkeypatch, 0.12, VideoTransform.HFLIP)

    assert options == ["--video-filter=transform{type='hflip'}:sharpen{sigma=0.12}"]


def test_sharpen_sigma_is_clamped_to_vlc_range(monkeypatch):
    assert _vlc_options(monkeypatch, -1.0) == []
    assert _vlc_options(monkeypatch, 3.0) == [
        "--video-filter=sharpen{sigma=2.00}"
    ]


def test_transient_preview_overrides_saved_setting_without_persisting(monkeypatch):
    monkeypatch.setattr(
        libvlc_options_parser, "Settings", lambda: _FakeSettings(0.08)
    )
    video = SimpleNamespace(transform=VideoTransform.NONE)

    libvlc_options_parser.set_sharpen_preview(0.21)
    assert libvlc_options_parser.get_vlc_options(video) == [
        "--video-filter=sharpen{sigma=0.21}"
    ]

    libvlc_options_parser.set_sharpen_preview(None)
    assert libvlc_options_parser.get_vlc_options(video) == [
        "--video-filter=sharpen{sigma=0.08}"
    ]


def test_sharpen_control_syncs_slider_and_spinbox():
    control = SharpenControl(0.10)

    assert control.enable_checkbox.isChecked()
    assert control.slider.minimum() == round(SHARPEN_STEP * 100)
    assert control.slider.maximum() == round(SHARPEN_UI_MAX * 100)
    assert control.spinbox.minimum() == SHARPEN_STEP
    assert control.spinbox.maximum() == SHARPEN_UI_MAX

    control.slider.setValue(23)
    assert control.value() == 0.23

    control.spinbox.setValue(0.17)
    assert control.slider.value() == 17


def test_sharpen_disabled_state_keeps_light_default_strength():
    control = SharpenControl(0.0)

    assert not control.enable_checkbox.isChecked()
    assert control.value() == 0.0
    assert control.spinbox.value() == SHARPEN_DEFAULT_STRENGTH
    assert not control.slider.isEnabled()
    assert not control.spinbox.isEnabled()
    assert not control.reset_button.isEnabled()


def test_sharpen_enable_and_reset_emit_committed_preview():
    control = SharpenControl(0.0)
    previews = []
    control.preview_requested.connect(previews.append)

    control.enable_checkbox.setChecked(True)
    assert previews == [SHARPEN_DEFAULT_STRENGTH]

    control.spinbox.setValue(0.20)
    assert previews == [SHARPEN_DEFAULT_STRENGTH]

    control.reset_button.click()
    assert control.value() == SHARPEN_DEFAULT_STRENGTH
    assert previews[-1] == SHARPEN_DEFAULT_STRENGTH

    control.enable_checkbox.setChecked(False)
    assert previews[-1] == 0.0


def test_sharpen_slider_and_spinbox_preview_only_after_committed_input():
    control = SharpenControl(0.10)
    previews = []
    control.preview_requested.connect(previews.append)

    control.slider.setValue(20)
    assert previews == []

    control.slider.sliderReleased.emit()
    assert previews == [0.20]

    control.spinbox.setValue(0.15)
    assert previews == [0.20]

    control.spinbox.editingFinished.emit()
    assert previews == [0.20, 0.15]


def test_sharpen_control_is_inserted_on_video_settings_page():
    dialog = SettingsDialog(None)
    control = attach_sharpen_control(dialog, 0.12)

    control_index = dialog.lay_page_defaults_video.indexOf(control)
    streaming_index = dialog.lay_page_defaults_video.indexOf(dialog.label_12)

    assert control.parent() is dialog.page_defaults_video
    assert control_index >= 0
    assert streaming_index == control_index + 1
    assert control.value() == 0.12
    assert control.title() == "Sharpen"


@pytest.mark.parametrize(
    ("result", "original", "preview", "final", "reloads"),
    [
        (QDialog.Accepted, 0.10, None, 0.10, 0),
        (QDialog.Accepted, 0.10, None, 0.20, 1),
        (QDialog.Accepted, 0.10, 0.20, 0.20, 0),
        (QDialog.Accepted, 0.10, 0.20, 0.10, 1),
        (QDialog.Rejected, 0.10, None, 0.20, 0),
        (QDialog.Rejected, 0.10, 0.20, 0.20, 1),
        (QDialog.Rejected, 0.10, 0.10, 0.20, 0),
    ],
)
def test_sharpen_dialog_close_refreshes_only_when_applied_state_must_change(
    monkeypatch, result, original, preview, final, reloads
):
    cleared = []
    monkeypatch.setattr(
        settings_manager_module, "set_sharpen_preview", cleared.append
    )
    fake_manager = SimpleNamespace(
        _sharpen_preview_value=preview,
        reload_video_filters=_FakeSignal(),
    )

    SettingsManager._finish_sharpen_preview(
        fake_manager,
        result,
        {SHARPEN_SETTING: original},
        final,
    )

    assert cleared == [None]
    assert fake_manager._sharpen_preview_value is None
    assert fake_manager.reload_video_filters.calls == reloads


def test_filter_refresh_reuses_video_state_with_current_position():
    class FakeBlock:
        def __init__(self):
            self.is_video_initialized = True
            self.video_tracks = {0: object()}
            self.video_params = SimpleNamespace(current_position=123456)
            self.set_video_calls = []

        def set_video(self, video):
            self.set_video_calls.append(video)

    block = FakeBlock()
    manager = SimpleNamespace(_ctx=SimpleNamespace(video_blocks=[block]))

    VideoBlocksManager.reload_video_filters(manager)

    assert block.set_video_calls == [block.video_params]
    assert block.set_video_calls[0].current_position == 123456


def test_vlc_initial_state_seeks_to_saved_position_while_playing():
    video = SimpleNamespace(
        current_position=123456,
        is_start_random=False,
        is_paused=False,
    )
    media_input = MediaInput(
        uri="C:/video.mp4",
        is_live=False,
        is_audio_only=False,
        size=(1920, 1080),
        video=video,
    )
    calls = []
    fake_player = SimpleNamespace(
        _log=_FakeLog(),
        media_input=media_input,
        _set_pause_initial=lambda paused: calls.append(("pause", paused)),
        _adjust_view_initial=lambda: calls.append(("view", None)),
        _set_time_initial=lambda position: calls.append(("time", position)),
    )

    VlcPlayerBase._set_initial_state(fake_player)

    assert media_input.initial_time == 123456
    assert calls == [
        ("pause", False),
        ("view", None),
        ("time", 123456),
    ]


def test_video_filter_reload_skips_known_audio_only_and_restarts_loading_blocks():
    class FakeBlock:
        def __init__(self, initialized, has_video, has_params=True):
            self.is_video_initialized = initialized
            self.video_tracks = {0: object()} if has_video else {}
            self.video_params = object() if has_params else None
            self.set_video_calls = []

        def set_video(self, video):
            self.set_video_calls.append(video)

    video = FakeBlock(initialized=True, has_video=True)
    audio = FakeBlock(initialized=True, has_video=False)
    loading = FakeBlock(initialized=False, has_video=False)
    empty = FakeBlock(initialized=False, has_video=False, has_params=False)
    manager = SimpleNamespace(
        _ctx=SimpleNamespace(video_blocks=[video, audio, loading, empty])
    )

    VideoBlocksManager.reload_video_filters(manager)

    assert video.set_video_calls == [video.video_params]
    assert audio.set_video_calls == []
    assert loading.set_video_calls == [loading.video_params]
    assert empty.set_video_calls == []
