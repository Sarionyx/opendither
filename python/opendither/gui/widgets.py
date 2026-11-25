"""Panel widgets: collapsible sections, scrubby sliders, segmented buttons, palette swatches."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QLayout, QMenu,
    QPushButton, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
)

LABEL_W = 86


class Section(QWidget):
    """Collapsible properties section with a caret header, like Adobe's Properties panel."""

    def __init__(self, title, extra=None, parent=None):
        super().__init__(parent)
        self.setObjectName("section")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 8, 0)
        self.btn = QToolButton()
        self.btn.setObjectName("sectionHead")
        self.btn.setText(title)
        self.btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn.setArrowType(Qt.DownArrow)
        self.btn.setCheckable(True)
        self.btn.setChecked(True)
        self.btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn.toggled.connect(self._toggle)
        head.addWidget(self.btn)
        if extra is not None:
            head.addWidget(extra)
        lay.addLayout(head)
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(12, 2, 12, 12)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(7)
        self.grid.setColumnMinimumWidth(0, LABEL_W)
        self.grid.setColumnStretch(1, 1)
        lay.addWidget(self.body)

    def _toggle(self, on):
        self.btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)

    def add_row(self, label, widget):
        r = self.grid.rowCount()
        if label is not None:
            lab = label if isinstance(label, QWidget) else field_label(label)
            self.grid.addWidget(lab, r, 0)
            self.grid.addWidget(widget, r, 1)
        else:
            self.grid.addWidget(widget, r, 0, 1, 2)
        return widget


def field_label(text):
    lab = QLabel(text)
    lab.setObjectName("fieldLabel")
    return lab


class ScrubLabel(QLabel):
    """Drag horizontally to change the value; double-click to reset (Adobe 'scrubby' label)."""
    scrubbed = Signal(float)   # delta in display units
    reset = Signal()

    def __init__(self, text, per_px):
        super().__init__(text)
        self.setObjectName("fieldLabel")
        self.setProperty("scrub", True)
        self.setCursor(QCursor(Qt.SizeHorCursor))
        self.setToolTip("Drag to adjust (Shift = fine) · double-click to reset")
        self.per_px = per_px
        self._x = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._x = e.position().x()

    def mouseMoveEvent(self, e):
        if self._x is None:
            return
        dx = e.position().x() - self._x
        self._x = e.position().x()
        fine = 0.1 if e.modifiers() & Qt.ShiftModifier else 1.0
        self.scrubbed.emit(dx * self.per_px * fine)

    def mouseReleaseEvent(self, e):
        self._x = None

    def mouseDoubleClickEvent(self, e):
        self.reset.emit()


class SliderField(QWidget):
    """Label | slider | number. Emits the *display* value."""
    valueChanged = Signal(float)

    def __init__(self, label, lo, hi, step=1.0, decimals=0, default=0.0):
        super().__init__()
        self.lo, self.hi, self.step, self.default = lo, hi, step, default
        self._acc = None
        self.factor = 10 ** decimals
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.label = ScrubLabel(label, (hi - lo) / 240.0)
        self.label.setFixedWidth(LABEL_W)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(round(lo * self.factor)), int(round(hi * self.factor)))
        self.slider.setSingleStep(max(1, int(round(step * self.factor))))
        self.spin = QDoubleSpinBox()
        self.spin.setRange(lo, hi)
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(step)
        self.spin.setAlignment(Qt.AlignRight)
        self.spin.setFixedWidth(50)
        self.spin.setKeyboardTracking(False)
        lay.addWidget(self.label)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(lambda v: self._emit(v / self.factor))
        self.spin.valueChanged.connect(self._emit)
        self.label.scrubbed.connect(self._scrub)
        self.label.reset.connect(lambda: self._emit(self.default))
        self.label.mouseReleaseEvent = self._scrub_end

    def _scrub(self, d):
        if self._acc is None:
            self._acc = self.spin.value()
        self._acc = min(self.hi, max(self.lo, self._acc + d))
        self._emit(round(self._acc / self.step) * self.step)

    def _scrub_end(self, e):
        self._acc = None
        self.label._x = None

    def _emit(self, v):
        v = min(self.hi, max(self.lo, float(v)))
        if abs(v - self.spin.value()) < 1e-9 and abs(v * self.factor - self.slider.value()) < 0.5 and self._acc is None:
            return
        self.set_value(v)
        self.valueChanged.emit(v)

    def set_value(self, v):
        for w in (self.slider, self.spin):
            w.blockSignals(True)
        self.slider.setValue(int(round(v * self.factor)))
        self.spin.setValue(v)
        for w in (self.slider, self.spin):
            w.blockSignals(False)

    def set_label(self, text):
        self.label.setText(text)


class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, options):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for i, (value, text, tip) in enumerate(options):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setProperty("seg", True)
            b.setProperty("segfirst", i == 0)
            b.setProperty("seglast", i == len(options) - 1)
            self.group.addButton(b)
            self.buttons[value] = b
            lay.addWidget(b, 1)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))

    def set_value(self, v):
        if v in self.buttons:
            self.buttons[v].setChecked(True)


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self.items = []
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if 0 <= i < len(self.items) else None

    def takeAt(self, i):
        return self.items.pop(i) if 0 <= i < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        m = self.contentsMargins()
        return QSize(60 + m.left() + m.right(), 30 + m.top() + m.bottom())

    def _layout(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = r.x(), r.y(), 0
        for it in self.items:
            sz = it.sizeHint()
            if x + sz.width() > r.right() + 1 and line_h > 0:
                x, y, line_h = r.x(), y + line_h + self.spacing(), 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), sz))
            x += sz.width() + self.spacing()
            line_h = max(line_h, sz.height())
        return y + line_h - rect.y() + m.bottom()


class SwatchBar(QWidget):
    """Editable palette: click a swatch to change it, right-click to remove, + to add."""
    edited = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("swatchBox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.flow = FlowLayout(self, 4)
        self.flow.setContentsMargins(6, 6, 6, 6)
        self.colors = []
        self.locked = False

    def set_colors(self, colors, locked=False):
        self.colors, self.locked = list(colors), locked
        while self.flow.count():
            w = self.flow.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, c in enumerate(self.colors):
            b = QToolButton()
            b.setFixedSize(22, 22)
            b.setStyleSheet(f"QToolButton {{ background: {c}; border: 1px solid #000; border-radius: 2px; }}"
                            f"QToolButton:hover {{ border: 1px solid #fff; }}")
            b.setToolTip(c + ("  (extracted)" if locked else "  · click to edit, right-click to remove"))
            if not locked:
                b.clicked.connect(lambda _=False, i=i: self._edit(i))
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda _p, i=i: self._menu(i))
            self.flow.addWidget(b)
        if not locked:
            add = QToolButton()
            add.setText("+")
            add.setFixedSize(22, 22)
            add.setToolTip("Add color")
            add.setStyleSheet("QToolButton { border: 1px solid #555; border-radius: 2px; color: #9b9b9b; }"
                              "QToolButton:hover { color: #fff; border-color: #888; }")
            add.clicked.connect(self._add)
            self.flow.addWidget(add)
        elif not self.colors:
            self.flow.addWidget(QLabel("Palette appears after render"))
        self.updateGeometry()

    def _edit(self, i):
        c = QColorDialog.getColor(QColor(self.colors[i]), self, "Palette color")
        if c.isValid():
            self.colors[i] = c.name()
            self.edited.emit(list(self.colors))

    def _menu(self, i):
        m = QMenu(self)
        rm = m.addAction("Remove color")
        rm.setEnabled(len(self.colors) > 1)
        dup = m.addAction("Duplicate")
        act = m.exec(QCursor.pos())
        if act is rm:
            del self.colors[i]
            self.edited.emit(list(self.colors))
        elif act is dup:
            self.colors.insert(i + 1, self.colors[i])
            self.edited.emit(list(self.colors))

    def _add(self):
        c = QColorDialog.getColor(QColor("#808080"), self, "Add color")
        if c.isValid():
            self.colors.append(c.name())
            self.edited.emit(list(self.colors))
