from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog

from gridplayer.dialogs.messagebox import QCustomMessageBox
from gridplayer.dialogs.settings import SettingsDialog
from gridplayer.dialogs.settings_color_adjust import attach_video_adjust_control
from gridplayer.dialogs.settings_sharpen import SHARPEN_SETTING, attach_sharpen_control
from gridplayer.params.theme import apply_theme
from gridplayer.player.managers.base import ManagerBase
from gridplayer.settings import Settings
from gridplayer.utils.libvlc_options_parser import (
    set_sharpen_preview,
    set_video_adjust_preview,
)
from gridplayer.utils.qt import translate
from gridplayer.utils.video_adjust import (
    CONTRAST_SETTING,
    SATURATION_SETTING,
    normalize_video_adjust_percent,
)


class SettingsManager(ManagerBase):
    reload = pyqtSignal()
    reload_video_filters = pyqtSignal()
    set_screensaver = pyqtSignal(int)
    set_log_level = pyqtSignal(int)
    set_log_level_vlc = pyqtSignal(int)
    set_recent_list_enabled = pyqtSignal(bool)
    keymap_changed = pyqtSignal(object)  # KeymapOverrides
    set_disable_mouse_click_events = pyqtSignal(bool)
    set_disable_mouse_wheel_events = pyqtSignal(bool)
    set_disable_overlay = pyqtSignal(bool)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sharpen_preview_value: float | None = None
        self._video_adjust_preview_value: tuple[int, int] | None = None

    @property
    def commands(self):
        return {"settings": self.cmd_settings}

    def cmd_settings(self):
        previous_settings = Settings().get_all()

        dialog = SettingsDialog(self.parent())
        sharpen_control = attach_sharpen_control(
            dialog, Settings().get(SHARPEN_SETTING)
        )
        video_adjust_control = attach_video_adjust_control(
            dialog,
            Settings().get(CONTRAST_SETTING),
            Settings().get(SATURATION_SETTING),
        )
        self._sharpen_preview_value = None
        self._video_adjust_preview_value = None
        sharpen_control.preview_requested.connect(self._apply_sharpen_preview)
        video_adjust_control.preview_requested.connect(self._apply_video_adjust_preview)

        result = dialog.exec_()
        final_sharpen = sharpen_control.value()
        final_video_adjust = video_adjust_control.values()

        if result == QDialog.Accepted:
            Settings().set(SHARPEN_SETTING, final_sharpen)
            Settings().set(CONTRAST_SETTING, final_video_adjust[0])
            Settings().set(SATURATION_SETTING, final_video_adjust[1])

        self._finish_video_filter_previews(
            result,
            previous_settings,
            final_sharpen,
            final_video_adjust,
        )
        self._apply_settings(previous_settings)

        if self._is_restart_needed(previous_settings):
            QCustomMessageBox.information(
                self.parent(),
                translate("Dialog - Settings apply restart", "Settings", "Header"),
                translate(
                    "Dialog - Settings apply restart",
                    "Restart is required for the new settings to take effect.",
                ),
            )

        if self._is_reload_needed(previous_settings):
            self.reload.emit()

    def _apply_sharpen_preview(self, value: float):
        value = round(float(value), 2)
        if value == self._sharpen_preview_value:
            return

        self._sharpen_preview_value = value
        set_sharpen_preview(value)
        self.reload_video_filters.emit()

    def _apply_video_adjust_preview(self, contrast: int, saturation: int):
        value = (
            normalize_video_adjust_percent(contrast),
            normalize_video_adjust_percent(saturation),
        )
        if value == self._video_adjust_preview_value:
            return

        self._video_adjust_preview_value = value
        set_video_adjust_preview(value)
        self.reload_video_filters.emit()

    def _finish_video_filter_previews(
        self,
        result,
        previous_settings,
        final_sharpen,
        final_video_adjust,
    ):
        original_sharpen = float(previous_settings[SHARPEN_SETTING])
        original_video_adjust = (
            int(previous_settings[CONTRAST_SETTING]),
            int(previous_settings[SATURATION_SETTING]),
        )
        applied_state = (
            original_sharpen
            if self._sharpen_preview_value is None
            else self._sharpen_preview_value,
            original_video_adjust
            if self._video_adjust_preview_value is None
            else self._video_adjust_preview_value,
        )
        desired_state = (
            (final_sharpen, final_video_adjust)
            if result == QDialog.Accepted
            else (original_sharpen, original_video_adjust)
        )

        set_sharpen_preview(None)
        set_video_adjust_preview(None)
        self._sharpen_preview_value = None
        self._video_adjust_preview_value = None

        if applied_state != desired_state:
            self.reload_video_filters.emit()

    def _apply_settings(self, previous_settings):
        checks = {
            "logging/log_level": self.set_log_level,
            "logging/log_level_vlc": self.set_log_level_vlc,
            "player/inhibit_screensaver": self.set_screensaver,
            "player/recent_list_enabled": self.set_recent_list_enabled,
            "player/keymap": self.keymap_changed,
            "playlist/disable_mouse_click_events": self.set_disable_mouse_click_events,
            "playlist/disable_mouse_wheel_events": self.set_disable_mouse_wheel_events,
            "playlist/disable_overlay": self.set_disable_overlay,
        }

        changes = self._setting_changes(previous_settings, tuple(checks))

        for c in changes:
            checks[c].emit(Settings().get(c))

        if self._is_setting_changed(previous_settings, "player/color_scheme"):
            apply_theme()

    def _is_reload_needed(self, previous_settings):
        checks = {
            "player/video_driver",
            "player/video_driver_players",
            "internal/opaque_hw_overlay",
            "internal/fake_overlay_invisibility",
            "misc/vlc_options",
        }

        return self._setting_changes(previous_settings, checks)

    def _is_restart_needed(self, previous_settings):
        checks = {
            "player/language",
            "logging/log_limit",
            "logging/log_limit_size",
            "logging/log_limit_backups",
            "player/stay_on_top",
        }

        return self._setting_changes(previous_settings, checks)

    def _setting_changes(self, previous_settings, checks):
        return {k for k in checks if previous_settings[k] != Settings().get(k)}

    def _is_setting_changed(self, previous_settings, check):
        return previous_settings[check] != Settings().get(check)
