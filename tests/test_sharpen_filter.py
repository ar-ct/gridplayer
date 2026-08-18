from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication

from gridplayer.dialogs.settings_sharpen import SHARPEN_UI_MAX, SharpenControl
from gridplayer.params.static import VideoTransform
from gridplayer.player.managers.video_blocks import VideoBlocksManager
from gridplayer.utils import libvlc_options_parser


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self, sigma):
        self.sigma = sigma

    def get(self, setting):
        assert setting == "player/sharpen_sigma"
        return self.sigma


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


def test_sharpen_control_syncs_slider_and_spinbox():
    control = SharpenControl(0.10)

    assert control.slider.minimum() == 0
    assert control.slider.maximum() == round(SHARPEN_UI_MAX * 100)
    assert control.spinbox.minimum() == 0.0
    assert control.spinbox.maximum() == SHARPEN_UI_MAX

    control.slider.setValue(23)
    assert control.value() == 0.23

    control.spinbox.setValue(0.17)
    assert control.slider.value() == 17


def test_sharpen_control_previews_only_after_committed_input():
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


def test_video_filter_reload_reuses_video_object_and_skips_non_video_blocks():
    class FakeBlock:
        def __init__(self, initialized, has_video):
            self.is_video_initialized = initialized
            self.video_tracks = {0: object()} if has_video else {}
            self.video_params = object()
            self.set_video_calls = []

        def set_video(self, video):
            self.set_video_calls.append(video)

    video = FakeBlock(initialized=True, has_video=True)
    audio = FakeBlock(initialized=True, has_video=False)
    loading = FakeBlock(initialized=False, has_video=True)
    manager = SimpleNamespace(
        _ctx=SimpleNamespace(video_blocks=[video, audio, loading])
    )

    VideoBlocksManager.reload_video_filters(manager)

    assert video.set_video_calls == [video.video_params]
    assert audio.set_video_calls == []
    assert loading.set_video_calls == []
