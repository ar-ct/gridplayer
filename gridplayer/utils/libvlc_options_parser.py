from gridplayer.models.video import Video
from gridplayer.params.static import VideoTransform
from gridplayer.settings import Settings

TransformMap = {
    VideoTransform.ROTATE_90: "90",
    VideoTransform.ROTATE_180: "180",
    VideoTransform.ROTATE_270: "270",
    VideoTransform.HFLIP: "hflip",
    VideoTransform.VFLIP: "vflip",
    VideoTransform.TRANSPOSE: "transpose",
    VideoTransform.ANTITRANSPOSE: "antitranspose",
}


def get_vlc_options(video_params: Video | None):
    if video_params is None:
        return []

    video_filters = []

    if video_params.transform != VideoTransform.NONE:
        option_str = TransformMap[video_params.transform]
        video_filters.append(f"transform{{type='{option_str}'}}")

    sharpen_sigma = max(0.0, min(Settings().get("player/sharpen_sigma"), 2.0))
    if sharpen_sigma > 0:
        video_filters.append(f"sharpen{{sigma={sharpen_sigma:.2f}}}")

    if not video_filters:
        return []

    return [f"--video-filter={':'.join(video_filters)}"]
