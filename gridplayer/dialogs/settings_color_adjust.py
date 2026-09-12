from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gridplayer.utils.video_adjust import (
    VIDEO_ADJUST_DEFAULT_PERCENT,
    VIDEO_ADJUST_MAX_PERCENT,
    VIDEO_ADJUST_MIN_PERCENT,
    VIDEO_ADJUST_STEP_PERCENT,
    normalize_video_adjust_percent,
)

_SLIDER_MAX = VIDEO_ADJUST_MAX_PERCENT // VIDEO_ADJUST_STEP_PERCENT


class VideoAdjustControl(QGroupBox):
    preview_requested = pyqtSignal(int, int)

    def __init__(
        self,
        contrast_percent: int,
        saturation_percent: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.setTitle(self.tr("Image adjustments"))

        self.contrast_slider = self._make_slider()
        self.saturation_slider = self._make_slider()
        self.contrast_value = QLabel(self)
        self.saturation_value = QLabel(self)
        self.contrast_value.setMinimumWidth(44)
        self.saturation_value.setMinimumWidth(44)
        self.contrast_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.saturation_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.addLayout(
            self._make_row(self.tr("Contrast"), self.contrast_slider, self.contrast_value)
        )
        layout.addLayout(
            self._make_row(
                self.tr("Saturation"), self.saturation_slider, self.saturation_value
            )
        )

        self.reset_button = QPushButton(self.tr("Reset"), self)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset_row.addWidget(self.reset_button)
        layout.addLayout(reset_row)

        self.setValues(contrast_percent, saturation_percent)

        self.contrast_slider.valueChanged.connect(self._update_value_labels)
        self.saturation_slider.valueChanged.connect(self._update_value_labels)
        self.contrast_slider.sliderReleased.connect(self._request_preview)
        self.saturation_slider.sliderReleased.connect(self._request_preview)
        self.reset_button.clicked.connect(self._reset)

    @staticmethod
    def _make_slider() -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, _SLIDER_MAX)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setTickInterval(1)
        return slider

    def _make_row(self, title: str, slider: QSlider, value_label: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(title, self)
        label.setMinimumWidth(76)
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        return row

    def values(self) -> tuple[int, int]:
        return (
            self.contrast_slider.value() * VIDEO_ADJUST_STEP_PERCENT,
            self.saturation_slider.value() * VIDEO_ADJUST_STEP_PERCENT,
        )

    def setValues(self, contrast_percent: int, saturation_percent: int) -> None:
        contrast = normalize_video_adjust_percent(contrast_percent)
        saturation = normalize_video_adjust_percent(saturation_percent)
        self.contrast_slider.setValue(contrast // VIDEO_ADJUST_STEP_PERCENT)
        self.saturation_slider.setValue(saturation // VIDEO_ADJUST_STEP_PERCENT)
        self._update_value_labels()

    def _update_value_labels(self, _value: int | None = None) -> None:
        contrast, saturation = self.values()
        self.contrast_value.setText(f"{contrast}%")
        self.saturation_value.setText(f"{saturation}%")

    def _reset(self) -> None:
        self.setValues(VIDEO_ADJUST_DEFAULT_PERCENT, VIDEO_ADJUST_DEFAULT_PERCENT)
        self._request_preview()

    def _request_preview(self) -> None:
        self.preview_requested.emit(*self.values())


def attach_video_adjust_control(
    dialog, contrast_percent: int, saturation_percent: int
) -> VideoAdjustControl:
    """Add global contrast/saturation controls to the existing Video settings page."""
    control = VideoAdjustControl(
        contrast_percent,
        saturation_percent,
        dialog.page_defaults_video,
    )
    insert_at = dialog.lay_page_defaults_video.indexOf(dialog.label_12)
    dialog.lay_page_defaults_video.insertWidget(insert_at, control)
    return control
