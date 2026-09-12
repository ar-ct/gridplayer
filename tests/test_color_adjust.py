from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

from gridplayer import settings as settings_module
from gridplayer.dialogs.settings import SettingsDialog
from gridplayer.dialogs.settings_color_adjust import (
    VideoAdjustControl,
    attach_video_adjust_control,
)
from gridplayer.dialogs.settings_sharpen import attach_sharpen_control
from gridplayer.params.static import VideoTransform
from gridplayer.player.managers import settings as settings_manager_module
from gridplayer.player.managers.settings import SettingsManager
from gridplayer.utils import libvlc_options_parser, video_adjust
from gridplayer.utils.video_adjust import (
    CONTRAST_SETTING,
    SATURATION_SETTING,
    VIDEO_ADJUST_DEFAULT_PERCENT,
    VIDEO_ADJUST_MAX_PERCENT,
    VIDEO_ADJUST_MIN_PERCENT,
    VIDEO_ADJUST_STEP_PERCENT,
)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])

    # A previous Qt test module can release its QApplication while the Python
    # Settings singleton still points at the QSettings C++ object owned by that
    # application lifetime. Recreate only that stale test singleton.
    if settings_module.SETTINGS is not None:
        try:
            settings_module.SETTINGS.settings.fileName()
        except RuntimeError:
            settings_module.SETTINGS = None

    return app


@pytest.fixture(autouse=True)
def _clear_filter_previews():
    libvlc_options_parser.set_sharpen_preview(None)
    libvlc_options_parser.set_video_adjust_preview(None)
    yield
    libvlc_options_parser.set_sharpen_preview(None)
    libvlc_options_parser.set_video_adjust_preview(None)


class _FakeSettings:
    def __init__(self, contrast=100, saturation=100, sharpen=0.0):
        self.values = {
            CONTRAST_SETTING: contrast,
            SATURATION_SETTING: saturation,
            "player/sharpen_sigma": sharpen,
        }

    def get(self, setting):
        return self.values[setting]


class _FakeSignal:
    def __init__(self):
        self.calls = 0

    def emit(self):
        self.calls += 1


def _vlc_options(
    monkeypatch,
    contrast=100,
    saturation=100,
    sharpen=0.0,
    transform=VideoTransform.NONE,
):
    fake_settings = _FakeSettings(contrast, saturation, sharpen)
    monkeypatch.setattr(libvlc_options_parser, "Settings", lambda: fake_settings)
    monkeypatch.setattr(video_adjust, "Settings", lambda: fake_settings)
    video = SimpleNamespace(transform=transform)
    return libvlc_options_parser.get_vlc_options(video)


def test_neutral_adjustment_adds_no_filter(monkeypatch):
    assert _vlc_options(monkeypatch) == []


def test_adjustment_composes_with_transform_and_sharpen(monkeypatch):
    options = _vlc_options(
        monkeypatch,
        contrast=120,
        saturation=80,
        sharpen=0.12,
        transform=VideoTransform.HFLIP,
    )

    assert options == [
        "--video-filter=transform{type='hflip'}:"
        "adjust{contrast=1.20,saturation=0.80}:sharpen{sigma=0.12}"
    ]


def test_adjustment_is_clamped_to_user_range(monkeypatch):
    assert _vlc_options(monkeypatch, contrast=300, saturation=-20) == [
        "--video-filter=adjust{contrast=2.00,saturation=0.00}"
    ]


def test_transient_adjustment_preview_overrides_saved_values(monkeypatch):
    fake_settings = _FakeSettings(contrast=120, saturation=80)
    monkeypatch.setattr(libvlc_options_parser, "Settings", lambda: fake_settings)
    monkeypatch.setattr(video_adjust, "Settings", lambda: fake_settings)
    video = SimpleNamespace(transform=VideoTransform.NONE)

    libvlc_options_parser.set_video_adjust_preview((70, 160))
    assert libvlc_options_parser.get_vlc_options(video) == [
        "--video-filter=adjust{contrast=0.70,saturation=1.60}"
    ]

    libvlc_options_parser.set_video_adjust_preview(None)
    assert libvlc_options_parser.get_vlc_options(video) == [
        "--video-filter=adjust{contrast=1.20,saturation=0.80}"
    ]


def test_control_has_exact_requested_range_and_step():
    control = VideoAdjustControl(100, 100)

    expected_max = VIDEO_ADJUST_MAX_PERCENT // VIDEO_ADJUST_STEP_PERCENT
    assert control.contrast_slider.minimum() == 0
    assert control.saturation_slider.minimum() == 0
    assert control.contrast_slider.maximum() == expected_max
    assert control.saturation_slider.maximum() == expected_max
    assert control.contrast_slider.singleStep() == 1
    assert control.saturation_slider.singleStep() == 1
    assert control.values() == (100, 100)

    control.contrast_slider.setValue(0)
    control.saturation_slider.setValue(expected_max)
    assert control.values() == (
        VIDEO_ADJUST_MIN_PERCENT,
        VIDEO_ADJUST_MAX_PERCENT,
    )
    assert control.contrast_value.text() == "0%"
    assert control.saturation_value.text() == "200%"


def test_slider_preview_is_committed_only_after_release():
    control = VideoAdjustControl(100, 100)
    previews = []
    control.preview_requested.connect(lambda c, s: previews.append((c, s)))

    control.contrast_slider.setValue(13)
    assert control.values() == (130, 100)
    assert previews == []

    control.contrast_slider.sliderReleased.emit()
    assert previews == [(130, 100)]

    control.saturation_slider.setValue(7)
    assert previews == [(130, 100)]
    control.saturation_slider.sliderReleased.emit()
    assert previews == [(130, 100), (130, 70)]


def test_reset_restores_neutral_and_requests_preview():
    control = VideoAdjustControl(50, 180)
    previews = []
    control.preview_requested.connect(lambda c, s: previews.append((c, s)))

    control.reset_button.click()

    assert control.values() == (
        VIDEO_ADJUST_DEFAULT_PERCENT,
        VIDEO_ADJUST_DEFAULT_PERCENT,
    )
    assert previews == [(100, 100)]


def test_control_is_inserted_on_video_page_after_sharpen():
    dialog = SettingsDialog(None)
    sharpen = attach_sharpen_control(dialog, 0.0)
    adjust = attach_video_adjust_control(dialog, 100, 100)

    sharpen_index = dialog.lay_page_defaults_video.indexOf(sharpen)
    adjust_index = dialog.lay_page_defaults_video.indexOf(adjust)
    streaming_index = dialog.lay_page_defaults_video.indexOf(dialog.label_12)

    assert sharpen.parent() is dialog.page_defaults_video
    assert adjust.parent() is dialog.page_defaults_video
    assert sharpen_index >= 0
    assert adjust_index == sharpen_index + 1
    assert streaming_index == adjust_index + 1
    assert adjust.title() == "Image adjustments"


def test_adjustment_settings_survive_settings_recreation(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module, "get_app_data_dir", lambda: tmp_path)

    current = settings_module._Settings()
    current.set(CONTRAST_SETTING, 130)
    current.set(SATURATION_SETTING, 70)
    current.sync()

    reopened = settings_module._Settings()
    assert reopened.get(CONTRAST_SETTING) == 130
    assert reopened.get(SATURATION_SETTING) == 70


@pytest.mark.parametrize(
    (
        "result",
        "original_sharpen",
        "sharpen_preview",
        "final_sharpen",
        "original_adjust",
        "adjust_preview",
        "final_adjust",
        "reloads",
    ),
    [
        (QDialog.Accepted, 0.10, None, 0.10, (100, 100), None, (100, 100), 0),
        (QDialog.Accepted, 0.10, None, 0.20, (100, 100), None, (120, 80), 1),
        (QDialog.Accepted, 0.10, 0.20, 0.20, (100, 100), (120, 80), (120, 80), 0),
        (QDialog.Rejected, 0.10, 0.20, 0.20, (100, 100), (120, 80), (120, 80), 1),
        (QDialog.Rejected, 0.10, 0.10, 0.20, (100, 100), (100, 100), (120, 80), 0),
    ],
)
def test_dialog_close_reconciles_all_video_filters_with_at_most_one_reload(
    monkeypatch,
    result,
    original_sharpen,
    sharpen_preview,
    final_sharpen,
    original_adjust,
    adjust_preview,
    final_adjust,
    reloads,
):
    cleared_sharpen = []
    cleared_adjust = []
    monkeypatch.setattr(
        settings_manager_module, "set_sharpen_preview", cleared_sharpen.append
    )
    monkeypatch.setattr(
        settings_manager_module, "set_video_adjust_preview", cleared_adjust.append
    )
    fake_manager = SimpleNamespace(
        _sharpen_preview_value=sharpen_preview,
        _video_adjust_preview_value=adjust_preview,
        reload_video_filters=_FakeSignal(),
    )
    previous = {
        "player/sharpen_sigma": original_sharpen,
        CONTRAST_SETTING: original_adjust[0],
        SATURATION_SETTING: original_adjust[1],
    }

    SettingsManager._finish_video_filter_previews(
        fake_manager,
        result,
        previous,
        final_sharpen,
        final_adjust,
    )

    assert cleared_sharpen == [None]
    assert cleared_adjust == [None]
    assert fake_manager._sharpen_preview_value is None
    assert fake_manager._video_adjust_preview_value is None
    assert fake_manager.reload_video_filters.calls == reloads
