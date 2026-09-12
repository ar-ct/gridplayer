from gridplayer.models.video import Video
from gridplayer.params.static import VideoTransform
from gridplayer.settings import Settings
from gridplayer.utils.video_adjust import (
    VIDEO_ADJUST_DEFAULT_PERCENT,
    get_saved_video_adjust,
    normalize_video_adjust_percent,
    percent_to_vlc_factor,
)

TransformMap = {
    VideoTransform.ROTATE_90: "90",
    VideoTransform.ROTATE_180: "180",
    VideoTransform.ROTATE_270: "270",
    VideoTransform.HFLIP: "hflip",
    VideoTransform.VFLIP: "vflip",
    VideoTransform.TRANSPOSE: "transpose",
    VideoTransform.ANTITRANSPOSE: "antitranspose",
}

_SHARPEN_PREVIEW: float | None = None
_VIDEO_ADJUST_PREVIEW: tuple[int, int] | None = None


def set_sharpen_preview(value: float | None) -> None:
    global _SHARPEN_PREVIEW
    _SHARPEN_PREVIEW = None if value is None else float(value)


def set_video_adjust_preview(value: tuple[int, int] | None) -> None:
    global _VIDEO_ADJUST_PREVIEW
    if value is None:
        _VIDEO_ADJUST_PREVIEW = None
        return

    _VIDEO_ADJUST_PREVIEW = (
        normalize_video_adjust_percent(value[0]),
        normalize_video_adjust_percent(value[1]),
    )


def get_vlc_options(video_params: Video | None):
    if video_params is None:
        return []

    video_filters = []

    if video_params.transform != VideoTransform.NONE:
        option_str = TransformMap[video_params.transform]
        video_filters.append(f"transform{{type='{option_str}'}}")

    contrast_percent, saturation_percent = (
        get_saved_video_adjust()
        if _VIDEO_ADJUST_PREVIEW is None
        else _VIDEO_ADJUST_PREVIEW
    )
    if (
        contrast_percent != VIDEO_ADJUST_DEFAULT_PERCENT
        or saturation_percent != VIDEO_ADJUST_DEFAULT_PERCENT
    ):
        contrast = percent_to_vlc_factor(contrast_percent)
        saturation = percent_to_vlc_factor(saturation_percent)
        video_filters.append(
            f"adjust{{contrast={contrast:.2f},saturation={saturation:.2f}}}"
        )

    sharpen_sigma = (
        Settings().get("player/sharpen_sigma")
        if _SHARPEN_PREVIEW is None
        else _SHARPEN_PREVIEW
    )
    sharpen_sigma = max(0.0, min(float(sharpen_sigma), 2.0))
    if sharpen_sigma > 0:
        video_filters.append(f"sharpen{{sigma={sharpen_sigma:.2f}}}")

    if not video_filters:
        return []

    return [f"--video-filter={':'.join(video_filters)}"]
