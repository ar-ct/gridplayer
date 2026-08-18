from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

SHARPEN_SETTING = "player/sharpen_sigma"
SHARPEN_UI_MAX = 0.50
SHARPEN_STEP = 0.01
SHARPEN_DEFAULT_STRENGTH = 0.05
_SHARPEN_SLIDER_SCALE = 100


class SharpenControl(QGroupBox):
    preview_requested = pyqtSignal(float)

    def __init__(self, value: float, parent: QWidget | None = None):
        super().__init__(parent)

        self.setTitle(self.tr("Sharpen"))

        self.enable_checkbox = QCheckBox(self.tr("Enable"), self)

        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(1, round(SHARPEN_UI_MAX * _SHARPEN_SLIDER_SCALE))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)

        self.spinbox = QDoubleSpinBox(self)
        self.spinbox.setRange(SHARPEN_STEP, SHARPEN_UI_MAX)
        self.spinbox.setDecimals(2)
        self.spinbox.setSingleStep(SHARPEN_STEP)
        self.spinbox.setMinimumWidth(78)

        self.reset_button = QPushButton(self.tr("Reset"), self)

        strength_label = QLabel(self.tr("Strength"), self)
        row = QHBoxLayout()
        row.addWidget(strength_label)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spinbox)
        row.addWidget(self.reset_button)

        hint = QLabel(
            self.tr(
                "Applies to all playing videos. Changes are applied after releasing "
                "the slider or finishing input. High-resolution video may use more CPU."
            ),
            self,
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.enable_checkbox)
        layout.addLayout(row)
        layout.addWidget(hint)

        self.setValue(value)

        self.enable_checkbox.stateChanged.connect(self._enabled_changed)
        self.slider.valueChanged.connect(self._slider_changed)
        self.spinbox.valueChanged.connect(self._spinbox_changed)
        self.slider.sliderReleased.connect(self._request_preview)
        self.spinbox.editingFinished.connect(self._request_preview)
        self.reset_button.clicked.connect(self._reset_strength)

    def value(self) -> float:
        if not self.enable_checkbox.isChecked():
            return 0.0
        return round(float(self.spinbox.value()), 2)

    def setValue(self, value: float) -> None:
        value = max(0.0, min(float(value), SHARPEN_UI_MAX))
        is_enabled = value > 0
        strength = value if is_enabled else SHARPEN_DEFAULT_STRENGTH

        self.enable_checkbox.setChecked(is_enabled)
        self.spinbox.setValue(strength)
        self.slider.setValue(round(strength * _SHARPEN_SLIDER_SCALE))
        self._set_strength_enabled(is_enabled)

    def _set_strength_enabled(self, is_enabled: bool) -> None:
        self.slider.setEnabled(is_enabled)
        self.spinbox.setEnabled(is_enabled)
        self.reset_button.setEnabled(is_enabled)

    def _enabled_changed(self, state: int) -> None:
        self._set_strength_enabled(state == Qt.Checked)
        self._request_preview()

    def _slider_changed(self, value: int) -> None:
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value / _SHARPEN_SLIDER_SCALE)
        self.spinbox.blockSignals(False)

    def _spinbox_changed(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(round(value * _SHARPEN_SLIDER_SCALE))
        self.slider.blockSignals(False)

    def _reset_strength(self) -> None:
        self.spinbox.setValue(SHARPEN_DEFAULT_STRENGTH)
        self._request_preview()

    def _request_preview(self) -> None:
        self.preview_requested.emit(self.value())


def attach_sharpen_control(dialog, value: float) -> SharpenControl:
    """Add the custom control to the existing Video settings page."""
    control = SharpenControl(value, dialog.page_defaults_video)
    insert_at = dialog.lay_page_defaults_video.indexOf(dialog.label_12)
    dialog.lay_page_defaults_video.insertWidget(insert_at, control)
    return control
