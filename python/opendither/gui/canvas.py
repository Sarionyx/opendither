"""Document canvas: zoom around cursor, pan, split before/after compare, drag & drop."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .theme import C

ZOOM_STEPS = [1 / 16, 1 / 12, 1 / 8, 1 / 6, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 1, 2, 3, 4, 5, 6, 8, 12, 16, 24, 32, 48, 64]


def _checker():
    pm = QPixmap(16, 16)
    pm.fill(QColor("#3a3a3a"))
    p = QPainter(pm)
    p.fillRect(0, 0, 8, 8, QColor("#2e2e2e"))
    p.fillRect(8, 8, 8, 8, QColor("#2e2e2e"))
    p.end()
    return pm


class Canvas(QWidget):
    viewChanged = Signal()
    fileDropped = Signal(str)
    toolRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("pasteboard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.original = None   # QPixmap
        self.result = None     # QPixmap (may be a smaller proxy; drawn in the same rect)
        self.zoom = 1.0        # 1.0 = one image pixel per *device* pixel
        self.ox = self.oy = 0.0
        self.tool = "hand"
        self.compare = False
        self.split = 0.5
        self.show_original = False
        self.space = False
        self._drag = None
        self._checker = QBrush(_checker())
        self.empty_text = "Drop an image here, paste one (Ctrl+V), or use File ▸ Open"

    # ---------------------------------------------------------------- content
    def set_original(self, pm):
        self.original = pm
        self.result = None
        self.fit()

    def set_result(self, pm):
        self.result = pm
        self.update()

    def clear(self):
        self.original = self.result = None
        self.update()
        self.viewChanged.emit()

    @property
    def img_w(self):
        return self.original.width() if self.original else 0

    @property
    def img_h(self):
        return self.original.height() if self.original else 0

    # ---------------------------------------------------------------- view
    def scale(self):
        return self.zoom / self.devicePixelRatioF()

    def image_rect(self):
        s = self.scale()
        return QRectF(self.ox, self.oy, self.img_w * s, self.img_h * s)

    def fit(self):
        if not self.original:
            return
        dpr = self.devicePixelRatioF()
        z = min((self.width() - 48) * dpr / self.img_w, (self.height() - 48) * dpr / self.img_h)
        if z > 1:
            z = math.floor(z)
        self.center(max(z, 1 / 32))

    def center(self, z):
        self.zoom = z
        s = self.scale()
        self.ox = round((self.width() - self.img_w * s) / 2)
        self.oy = round((self.height() - self.img_h * s) / 2)
        self._changed()

    def zoom_at(self, z, cx=None, cy=None):
        if not self.original:
            return
        z = min(64.0, max(1 / 32, z))
        if cx is None:
            cx, cy = self.width() / 2, self.height() / 2
        s0 = self.scale()
        ix, iy = (cx - self.ox) / s0, (cy - self.oy) / s0
        self.zoom = z
        s1 = self.scale()
        self.ox, self.oy = cx - ix * s1, cy - iy * s1
        self._changed()

    def step_zoom(self, direction, cx=None, cy=None):
        z = self.zoom
        if direction > 0:
            nxt = next((s for s in ZOOM_STEPS if s > z + 1e-6), z)
        else:
            nxt = next((s for s in reversed(ZOOM_STEPS) if s < z - 1e-6), z)
        self.zoom_at(nxt, cx, cy)

    def visible_image_rect(self):
        """Visible area in image pixel coordinates (for the navigator)."""
        s = self.scale()
        x0, y0 = max(0, -self.ox / s), max(0, -self.oy / s)
        x1 = min(self.img_w, (self.width() - self.ox) / s)
        y1 = min(self.img_h, (self.height() - self.oy) / s)
        return QRectF(x0, y0, max(0, x1 - x0), max(0, y1 - y0))

    def center_on(self, ix, iy):
        s = self.scale()
        self.ox, self.oy = self.width() / 2 - ix * s, self.height() / 2 - iy * s
        self._changed()

    def _changed(self):
        self.update()
        self.viewChanged.emit()

    def set_tool(self, tool):
        self.tool = tool
        self._update_cursor()

    def _update_cursor(self, alt=False):
        if self._drag and self._drag[0] == "pan":
            self.setCursor(Qt.ClosedHandCursor)
        elif self.space or self.tool == "hand":
            self.setCursor(Qt.OpenHandCursor)
        elif self.tool == "zoom":
            self.setCursor(Qt.CrossCursor if not alt else Qt.ArrowCursor)
        elif self.tool == "compare":
            self.setCursor(Qt.SplitHCursor)

    # ---------------------------------------------------------------- painting
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C["pasteboard"]))
        if not self.original:
            p.setPen(QColor(C["faint"]))
            p.drawText(self.rect(), Qt.AlignCenter, self.empty_text)
            return
        r = self.image_rect()
        # drop shadow + border
        p.fillRect(r.adjusted(-1, -1, 1, 1), QColor("#000"))
        p.fillRect(r, self._checker)
        p.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1)
        show_result = self.result is not None and not self.show_original
        if not show_result:
            p.drawPixmap(r, self.original, QRectF(self.original.rect()))
        elif self.compare:
            p.drawPixmap(r, self.original, QRectF(self.original.rect()))
            sx = r.x() + r.width() * self.split
            p.save()
            p.setClipRect(QRectF(sx, r.y(), r.right() - sx + 1, r.height()))
            p.drawPixmap(r, self.result, QRectF(self.result.rect()))
            p.restore()
        else:
            p.drawPixmap(r, self.result, QRectF(self.result.rect()))
        if self.compare and self.result is not None:
            sx = r.x() + r.width() * self.split
            top, bot = max(0.0, r.y()), min(float(self.height()), r.bottom())
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(QColor(0, 0, 0, 130), 3))
            p.drawLine(QPointF(sx, top), QPointF(sx, bot))
            p.setPen(QPen(QColor(255, 255, 255, 230), 1))
            p.drawLine(QPointF(sx, top), QPointF(sx, bot))
            cy = (top + bot) / 2
            p.setBrush(QColor(C["accent"]))
            p.setPen(QPen(QColor("#fff"), 2))
            p.drawEllipse(QPointF(sx, cy), 11, 11)
            p.setBrush(QColor("#fff"))
            p.setPen(Qt.NoPen)
            for d in (-1, 1):
                pts = [QPointF(sx + d * 7, cy), QPointF(sx + d * 2.5, cy - 4), QPointF(sx + d * 2.5, cy + 4)]
                p.drawPolygon(pts)

    # ---------------------------------------------------------------- input
    def mousePressEvent(self, e):
        if not self.original:
            return
        pos = e.position()
        pan = e.button() == Qt.MiddleButton or self.space or (self.tool == "hand" and e.button() == Qt.LeftButton)
        if self.tool == "zoom" and not self.space and e.button() == Qt.LeftButton:
            self.step_zoom(-1 if e.modifiers() & Qt.AltModifier else 1, pos.x(), pos.y())
            return
        if pan:
            self._drag = ("pan", pos.x(), pos.y(), self.ox, self.oy)
            self._update_cursor()
        elif self.tool == "compare" and e.button() == Qt.LeftButton:
            self._drag = ("split",)
            self._move_split(pos.x())

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        pos = e.position()
        if self._drag[0] == "pan":
            _, sx, sy, ox, oy = self._drag
            self.ox, self.oy = ox + pos.x() - sx, oy + pos.y() - sy
            self._changed()
        else:
            self._move_split(pos.x())

    def mouseReleaseEvent(self, e):
        self._drag = None
        self._update_cursor()

    def _move_split(self, x):
        r = self.image_rect()
        self.split = min(1.0, max(0.0, (x - r.x()) / max(1.0, r.width())))
        self.update()

    def wheelEvent(self, e):
        if not self.original:
            return
        dy = e.angleDelta().y()
        pos = e.position()
        if e.modifiers() & Qt.ShiftModifier:
            self.ox += dy / 2
            self._changed()
            return
        self.zoom_at(self.zoom * math.exp(dy * 0.0018), pos.x(), pos.y())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self.space = True
            self._update_cursor()
        elif e.key() == Qt.Key_Backslash and not e.isAutoRepeat():
            self.show_original = True
            self.update()
        elif e.key() == Qt.Key_Alt:
            self._update_cursor(alt=True)
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self.space = False
            self._update_cursor()
        elif e.key() == Qt.Key_Backslash and not e.isAutoRepeat():
            self.show_original = False
            self.update()
        elif e.key() == Qt.Key_Alt:
            self._update_cursor()
        else:
            super().keyReleaseEvent(e)

    def resizeEvent(self, e):
        self.viewChanged.emit()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.fileDropped.emit(urls[0].toLocalFile())


class Navigator(QWidget):
    """Thumbnail with the visible-area rectangle; click or drag to move the view."""

    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.thumb = None
        self.setMinimumHeight(140)
        self.setCursor(Qt.PointingHandCursor)
        canvas.viewChanged.connect(self.update)

    def set_source(self, pm):
        self.thumb = pm
        self.update()

    def _geom(self):
        cw, ch = self.canvas.img_w, self.canvas.img_h
        if not cw:
            return None
        s = min((self.width() - 8) / cw, (self.height() - 8) / ch)
        w, h = cw * s, ch * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), s

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C["pasteboard"]))
        g = self._geom()
        if not g or not self.thumb:
            return
        r, s = g
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(r, self.thumb, QRectF(self.thumb.rect()))
        v = self.canvas.visible_image_rect()
        if v.width() > 0 and v.height() > 0:
            vr = QRectF(r.x() + v.x() * s, r.y() + v.y() * s, v.width() * s, v.height() * s)
            p.setPen(QPen(QColor(0, 0, 0, 160), 3))
            p.drawRect(vr)
            p.setPen(QPen(QColor("#ff4a4a"), 1))
            p.drawRect(vr)

    def _jump(self, pos):
        g = self._geom()
        if g:
            r, s = g
            self.canvas.center_on((pos.x() - r.x()) / s, (pos.y() - r.y()) / s)

    def mousePressEvent(self, e):
        self._jump(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._jump(e.position())
