from gridplayer.settings import Settings

CONTRAST_SETTING = "player/video_contrast"
SATURATION_SETTING = "player/video_saturation"

VIDEO_ADJUST_MIN_PERCENT = 0
VIDEO_ADJUST_MAX_PERCENT = 200
VIDEO_ADJUST_STEP_PERCENT = 10
VIDEO_ADJUST_DEFAULT_PERCENT = 100


def normalize_video_adjust_percent(value: int | float) -> int:
    value = max(
        VIDEO_ADJUST_MIN_PERCENT,
        min(float(value), VIDEO_ADJUST_MAX_PERCENT),
    )
    steps = int((value + VIDEO_ADJUST_STEP_PERCENT / 2) // VIDEO_ADJUST_STEP_PERCENT)
    return steps * VIDEO_ADJUST_STEP_PERCENT


def percent_to_vlc_factor(value: int | float) -> float:
    return normalize_video_adjust_percent(value) / 100.0


def get_saved_video_adjust() -> tuple[int, int]:
    return (
        normalize_video_adjust_percent(Settings().get(CONTRAST_SETTING)),
        normalize_video_adjust_percent(Settings().get(SATURATION_SETTING)),
    )
