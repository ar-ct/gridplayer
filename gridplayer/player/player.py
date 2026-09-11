from functools import partial

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut, QWidget

from gridplayer.params import env
from gridplayer.player.manager import ManagersManager
from gridplayer.player.managers.actions import ActionsManager
from gridplayer.player.managers.active_block import ActiveBlockManager
from gridplayer.player.managers.add_videos import AddVideosManager
from gridplayer.player.managers.dialogs import DialogsManager
from gridplayer.player.managers.drag_n_drop import DragNDropManager
from gridplayer.player.managers.grid import GridManager
from gridplayer.player.managers.instance_listener import InstanceListenerManager
from gridplayer.player.managers.log import LogManager
from gridplayer.player.managers.macos_fileopen import MacOSFileOpenManager
from gridplayer.player.managers.menu import MenuManager
from gridplayer.player.managers.mouse_hide import MouseHideManager
from gridplayer.player.managers.playlist import PlaylistManager
from gridplayer.player.managers.recent_list import RecentListManager
from gridplayer.player.managers.screensaver import ScreensaverManager
from gridplayer.player.managers.settings import SettingsManager
from gridplayer.player.managers.single_mode import SingleModeManager
from gridplayer.player.managers.snapshots import SnapshotsManager
from gridplayer.player.managers.stream_proxy import StreamProxyManager
from gridplayer.player.managers.video_blocks import VideoBlocksManager
from gridplayer.player.managers.video_driver import VideoDriverManager
from gridplayer.player.managers.window_state import WindowStateManager
from gridplayer.utils.cell_random import (
    CELL_RANDOM_SHORTCUT_KEYS,
    CellRandomController,
    release_digit_seek_shortcuts,
)
from gridplayer.utils.playback_rate import (
    GLOBAL_PLAYBACK_RATE_DECREASE_KEY,
    GLOBAL_PLAYBACK_RATE_INCREASE_KEY,
    GLOBAL_PLAYBACK_RATE_RESET_KEY,
    GlobalPlaybackRateController,
)


class Player(QWidget, ManagersManager):
    arguments_received = pyqtSignal(list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self.managers = {
            "video_driver": VideoDriverManager,
            "window_state": WindowStateManager,
            "video_blocks": VideoBlocksManager,
            "grid": GridManager,
            "playlist": PlaylistManager,
            "snapshots": SnapshotsManager,
            "screensaver": ScreensaverManager,
            "active_block": ActiveBlockManager,
            "mouse_hide": MouseHideManager,
            "drag_n_drop": DragNDropManager,
            "single_mode": SingleModeManager,
            "log": LogManager,
            "stream_proxy": StreamProxyManager,
            "add_videos": AddVideosManager,
            "recent_list": RecentListManager,
            "dialogs": DialogsManager,
            "settings": SettingsManager,
            "actions": ActionsManager,
            "menu": MenuManager,
        }

        self.connections = {
            "window_state": [
                ("pause_on_minimize", "video_blocks.cmd_all_pause"),
            ],
            "grid": [
                ("minimum_size_changed", "window_state.set_minimum_size"),
                ("video_blocks.video_count_changed", "reload_video_grid"),
                ("video_blocks.video_order_changed", "reload_video_grid"),
            ],
            "screensaver": [
                ("video_blocks.playings_videos_count_changed", "screensaver_check")
            ],
            "mouse_hide": [
                ("video_blocks.video_count_changed", "show_cursor"),
            ],
            "active_block": [
                ("video_blocks.video_count_changed", "update_active_under_mouse")
            ],
            "drag_n_drop": [
                ("videos_swapped", "grid.reload_video_grid"),
                ("videos_dropped", "video_blocks.add_videos"),
                ("videos_dropped", "window_state.activate_window"),
                ("videos_dropped", "recent_list.add_recent_videos"),
                ("playlist_dropped", "playlist.load_playlist_file"),
            ],
            "single_mode": [
                ("mode_changed", "grid.adapt_grid"),
                ("video_blocks.video_count_changed", "set_video_count"),
            ],
            "video_blocks": [
                ("reload_all_closed", "video_driver.cleanup"),
            ],
            "settings": [
                ("reload", "video_blocks.reload_videos"),
                ("reload_video_filters", "video_blocks.reload_video_filters"),
                ("set_screensaver", "screensaver.screensaver_check"),
                ("set_log_level", "log.set_log_level"),
                ("set_log_level", "video_driver.set_log_level"),
                ("set_log_level_vlc", "video_driver.set_log_level_vlc"),
                ("set_recent_list_enabled", "recent_list.set_recent_list_state"),
                ("keymap_changed", "actions.apply_bindings"),
                (
                    "set_disable_mouse_click_events",
                    "video_blocks.set_disable_mouse_click_events",
                ),
                (
                    "set_disable_mouse_wheel_events",
                    "video_blocks.set_disable_mouse_wheel_events",
                ),
                ("set_disable_overlay", "video_blocks.set_disable_overlay"),
            ],
            "playlist": [
                ("s.arguments_received", "process_arguments"),
                ("playlist_file_loaded", "recent_list.add_recent_playlist"),
                ("playlist_saved", "recent_list.add_recent_playlist"),
                ("playlist_closed", "video_blocks.close_all"),
                ("playlist_closed", "window_state.restore_to_minimum"),
                ("video_blocks.video_count_changed", "on_video_count_changed"),
                ("window_state_loaded", "window_state.restore_window_state"),
                ("grid_state_loaded", "grid.set_grid_state"),
                ("snapshots_loaded", "snapshots.set_snapshots"),
                ("seek_sync_mode_loaded", "video_blocks.set_seek_sync_mode"),
                ("shuffle_on_load_loaded", "video_blocks.set_shuffle_on_load"),
                (
                    "disable_mouse_click_events_loaded",
                    "video_blocks.set_disable_mouse_click_events",
                ),
                (
                    "disable_mouse_wheel_events_loaded",
                    "video_blocks.set_disable_mouse_wheel_events",
                ),
                (
                    "disable_overlay_loaded",
                    "video_blocks.set_disable_overlay",
                ),
                ("videos_loaded", "video_blocks.add_videos"),
                ("alert", "window_state.activate_window"),
                ("error", "dialogs.error"),
            ],
            "snapshots": [
                ("grid_state_loaded", "grid.set_grid_state"),
                ("video_blocks.video_count_changed", "clear_snapshots"),
                ("warning", "dialogs.warning"),
            ],
            "add_videos": [
                ("videos_added", "video_blocks.add_videos"),
                ("videos_added", "window_state.activate_window"),
                ("videos_added", "recent_list.add_recent_videos"),
                ("error", "dialogs.error"),
            ],
            "recent_list": [
                ("videos_added", "video_blocks.add_videos"),
                ("videos_added", "window_state.activate_window"),
                ("playlist_opened", "playlist.load_playlist_file"),
                ("error", "dialogs.error"),
            ],
        }

        if env.IS_MACOS:
            self.managers["macos_fileopen"] = MacOSFileOpenManager
            self.connections["macos_fileopen"] = [
                ("file_opened", "playlist.process_arguments")
            ]
            self.global_event_filters.append("macos_fileopen")
        else:
            self.managers["instance_listener"] = InstanceListenerManager
            self.connections["instance_listener"] = [
                ("files_opened", "playlist.process_arguments"),
                ("window_state.closing", "cleanup"),
            ]

        self.global_event_filters.append("mouse_hide")

        self.event_filters = [
            "window_state",
            "drag_n_drop",
            "active_block",
            "menu",
            # After other filters: only consumes when a mouse chord matches.
            # Receives events targeted at the Player (empty chrome), not VideoBlocks.
            "actions",
        ]

        self.init()

        # Custom build: preserve PgDown's original alphabetical behavior and
        # provide explicit one-key random-next commands on unused keys.
        self.random_next_shortcut = QShortcut(QKeySequence("End"), self)
        self.random_next_shortcut.activated.connect(
            self._context.commands.resolve(("active", "shuffle_video"))
        )

        self.random_next_all_shortcut = QShortcut(QKeySequence("Home"), self)
        self.random_next_all_shortcut.activated.connect(self._shuffle_all_videos)

        # Custom build: bare digits 1-9 target a specific grid cell regardless
        # of focus. Keep the old 10%-90% seek actions available from the menu,
        # but release their bare digit shortcuts so Qt never sees ambiguity.
        self.cell_random = CellRandomController(lambda: self._context.video_blocks)
        self._reserve_cell_random_digit_shortcuts()
        self._managers_inst["settings"].keymap_changed.connect(
            self._reserve_cell_random_digit_shortcuts
        )

        self.cell_random_shortcuts = []
        for cell_number, key in enumerate(CELL_RANDOM_SHORTCUT_KEYS, start=1):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(partial(self.cell_random.shuffle_cell, cell_number))
            self.cell_random_shortcuts.append(shortcut)

        # Custom build: one runtime-only playback rate for every cell. The
        # controller is deliberately not backed by Settings, so every process
        # starts at 100% and closing the application discards the current rate.
        self.global_playback_rate = GlobalPlaybackRateController(
            lambda: self._context.video_blocks
        )

        self.global_rate_increase_shortcut = QShortcut(
            QKeySequence(GLOBAL_PLAYBACK_RATE_INCREASE_KEY), self
        )
        self.global_rate_increase_shortcut.activated.connect(
            self.global_playback_rate.increase
        )

        self.global_rate_decrease_shortcut = QShortcut(
            QKeySequence(GLOBAL_PLAYBACK_RATE_DECREASE_KEY), self
        )
        self.global_rate_decrease_shortcut.activated.connect(
            self.global_playback_rate.decrease
        )

        self.global_rate_reset_shortcut = QShortcut(
            QKeySequence(GLOBAL_PLAYBACK_RATE_RESET_KEY), self
        )
        self.global_rate_reset_shortcut.activated.connect(
            self.global_playback_rate.reset
        )

        # New blocks inherit the current runtime rate. Existing blocks are not
        # reset merely because another block was closed.
        self._managers_inst["video_blocks"].video_count_changed.connect(
            self.global_playback_rate.apply_to_new_blocks
        )
        self.global_playback_rate.apply_to_new_blocks()

    def _reserve_cell_random_digit_shortcuts(self, _overrides=None):
        release_digit_seek_shortcuts(self._context.actions)

    def _shuffle_all_videos(self):
        for video_block in self._context.video_blocks:
            video_block.shuffle_video()

    def process_arguments(self, argv):
        self.arguments_received.emit(argv)
