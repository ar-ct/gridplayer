from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

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


def attach_sharpen_control(dialog, value: float) -> SharpenControl:
    """Add the custom control to the existing Video settings page."""
    control = SharpenControl(value, dialog.page_defaults_video)
    insert_at = dialog.lay_page_defaults_video.indexOf(dialog.label_12)
    dialog.lay_page_defaults_video.insertWidget(insert_at, control)
    return control
