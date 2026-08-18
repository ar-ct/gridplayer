from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gridplayer.dialogs.settings import SettingsDialog as BaseSettingsDialog
from gridplayer.settings import Settings

SHARPEN_SETTING = "player/sharpen_sigma"
SHARPEN_UI_MAX = 0.50
SHARPEN_STEP = 0.01
_SHARPEN_SLIDER_SCALE = 100


class SharpenControl(QGroupBox):
    preview_requested = pyqtSignal(float)

    def __init__(self, value: float, parent: QWidget | None = None):
        super().__init__(parent)

        self.setTitle(self.tr("Sharpen"))

        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, round(SHARPEN_UI_MAX * _SHARPEN_SLIDER_SCALE))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)

        self.spinbox = QDoubleSpinBox(self)
        self.spinbox.setRange(0.0, SHARPEN_UI_MAX)
        self.spinbox.setDecimals(2)
        self.spinbox.setSingleStep(SHARPEN_STEP)
        self.spinbox.setSpecialValueText(self.tr("Off"))
        self.spinbox.setMinimumWidth(78)

        strength_label = QLabel(self.tr("Strength"), self)
        row = QHBoxLayout()
        row.addWidget(strength_label)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spinbox)

        hint = QLabel(
            self.tr(
                "0 = Off. Applies to all playing videos. "
                "Changes are applied after releasing the slider or finishing input."
            ),
            self,
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(hint)

        self.slider.valueChanged.connect(self._slider_changed)
        self.spinbox.valueChanged.connect(self._spinbox_changed)
        self.slider.sliderReleased.connect(self._request_preview)
        self.spinbox.editingFinished.connect(self._request_preview)

        self.setValue(value)

    def value(self) -> float:
        return round(float(self.spinbox.value()), 2)

    def setValue(self, value: float) -> None:
        value = max(0.0, min(float(value), SHARPEN_UI_MAX))
        self.spinbox.setValue(value)
        self.slider.setValue(round(value * _SHARPEN_SLIDER_SCALE))

    def _slider_changed(self, value: int) -> None:
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value / _SHARPEN_SLIDER_SCALE)
        self.spinbox.blockSignals(False)

    def _spinbox_changed(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(round(value * _SHARPEN_SLIDER_SCALE))
        self.slider.blockSignals(False)

    def _request_preview(self) -> None:
        self.preview_requested.emit(self.value())


class SettingsDialog(BaseSettingsDialog):
    sharpen_preview = pyqtSignal(float)

    def __init__(self, parent):
        super().__init__(parent)

        initial_value = Settings().get(SHARPEN_SETTING)
        self._last_sharpen_preview = round(float(initial_value), 2)
        self.sharpenControl = SharpenControl(initial_value, self.page_defaults_video)
        self.sharpenControl.preview_requested.connect(self._preview_sharpen)

        insert_at = self.lay_page_defaults_video.indexOf(self.label_12)
        self.lay_page_defaults_video.insertWidget(insert_at, self.sharpenControl)

    def _preview_sharpen(self, value: float) -> None:
        value = round(float(value), 2)
        if value == self._last_sharpen_preview:
            return

        self._last_sharpen_preview = value
        self.sharpen_preview.emit(value)

    def save_settings(self):
        super().save_settings()
        Settings().set(SHARPEN_SETTING, self.sharpenControl.value())

    def accept(self):
        self._preview_sharpen(self.sharpenControl.value())
        self.save_settings()
        QDialog.accept(self)
