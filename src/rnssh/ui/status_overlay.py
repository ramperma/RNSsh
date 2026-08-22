"""Floating translucent status overlay for AI/voice feedback."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class StatusOverlay(QWidget):
    """Small always-on-top card (icon + text) that pulses while active."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._icon = QLabel()
        self._icon.setObjectName("overlayIcon")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text = QLabel()
        self._text.setObjectName("overlayText")
        self._text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("overlayCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 12, 20, 12)
        row.setSpacing(12)
        row.addWidget(self._icon)
        row.addWidget(self._text)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        self._pulse = QPropertyAnimation(self, b"windowOpacity", self)
        self._pulse.setDuration(700)
        self._pulse.setStartValue(1.0)
        self._pulse.setEndValue(0.55)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)

    def show_state(self, text: str, icon: str = "🤖") -> None:
        self._icon.setText(icon)
        self._text.setText(text)
        self.adjustSize()
        self._center()
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self._pulse.start()

    def hide_state(self) -> None:
        self._pulse.stop()
        self.setWindowOpacity(1.0)
        self.hide()

    def _center(self) -> None:
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            geo = parent.frameGeometry()
        else:
            screen = self.screen()
            geo = screen.availableGeometry() if screen is not None else None
        if geo is None:
            return
        self.move(geo.center() - self.rect().center())
