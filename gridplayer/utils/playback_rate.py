GLOBAL_PLAYBACK_RATE_MIN_PERCENT = 50
GLOBAL_PLAYBACK_RATE_MAX_PERCENT = 200
GLOBAL_PLAYBACK_RATE_STEP_PERCENT = 10
GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT = 100

GLOBAL_PLAYBACK_RATE_INCREASE_KEY = "Shift+Up"
GLOBAL_PLAYBACK_RATE_DECREASE_KEY = "Shift+Down"
GLOBAL_PLAYBACK_RATE_RESET_KEY = "Insert"


class GlobalPlaybackRateController:
    """Keep one non-persistent playback rate for all video blocks."""

    def __init__(self, video_blocks_provider):
        self._video_blocks_provider = video_blocks_provider
        self._percent = GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT
        self._known_block_ids = set()

    @property
    def percent(self):
        return self._percent

    @property
    def rate(self):
        return self._percent / 100.0

    @staticmethod
    def _apply_rate_to_video_block(video_block, rate):
        if video_block.video_params is None:
            return

        # Keep the rate in the in-memory Video model. VideoBlock reuses that
        # model when switching files, so the rate survives file navigation.
        video_block.video_params.rate = rate

        # A block that is still loading will apply video_params.rate in
        # load_video_finish(). Initialized blocks are updated immediately.
        if video_block.is_video_initialized:
            video_block.set_rate(rate)

    def set_percent(self, percent):
        self._percent = max(
            GLOBAL_PLAYBACK_RATE_MIN_PERCENT,
            min(int(percent), GLOBAL_PLAYBACK_RATE_MAX_PERCENT),
        )

        current_ids = set()
        for video_block in self._video_blocks_provider():
            current_ids.add(video_block.id)
            self._apply_rate_to_video_block(video_block, self.rate)

        self._known_block_ids = current_ids

    def increase(self):
        self.set_percent(self._percent + GLOBAL_PLAYBACK_RATE_STEP_PERCENT)

    def decrease(self):
        self.set_percent(self._percent - GLOBAL_PLAYBACK_RATE_STEP_PERCENT)

    def reset(self):
        self.set_percent(GLOBAL_PLAYBACK_RATE_DEFAULT_PERCENT)

    def apply_to_new_blocks(self, _video_count=None):
        current_ids = set()

        for video_block in self._video_blocks_provider():
            current_ids.add(video_block.id)
            if video_block.id in self._known_block_ids:
                continue
            self._apply_rate_to_video_block(video_block, self.rate)

        # Dropped IDs are forgotten, so a future block can safely be treated
        # as new even if object IDs are ever reused.
        self._known_block_ids = current_ids
