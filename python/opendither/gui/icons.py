"""Inline SVG icons rendered to QIcons (same drawings as the web app)."""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

SVG = {
    "hand": '<svg viewBox="0 0 20 20" fill="none" stroke="{c}" stroke-width="1.4" stroke-linejoin="round"><path d="M6 10V5.2a1.2 1.2 0 0 1 2.4 0V9m0-4.8V3.7a1.2 1.2 0 0 1 2.4 0V9m0-4.6a1.2 1.2 0 0 1 2.4 0V9.5m0-3a1.2 1.2 0 0 1 2.4 0v5.3c0 3.3-2.4 5.7-5.6 5.7-2.2 0-3.4-.9-4.6-2.6L3.2 11.6a1.3 1.3 0 0 1 2-1.6L6 11"/></svg>',
    "zoom": '<svg viewBox="0 0 20 20" fill="none" stroke="{c}" stroke-width="1.5"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.6 12.6 17 17M6 8.5h5M8.5 6v5" stroke-linecap="round"/></svg>',
    "compare": '<svg viewBox="0 0 20 20" fill="none" stroke="{c}" stroke-width="1.4"><rect x="2.5" y="3.5" width="15" height="13" rx="1.5"/><path d="M10 1.5v17"/><path d="M10.7 3.5h5.3a1.5 1.5 0 0 1 1.5 1.5v10a1.5 1.5 0 0 1-1.5 1.5h-5.3z" fill="{c}" stroke="none" opacity=".55"/></svg>',
    "original": '<svg viewBox="0 0 20 20" fill="none" stroke="{c}" stroke-width="1.4"><path d="M1.8 10S5 4.5 10 4.5 18.2 10 18.2 10 15 15.5 10 15.5 1.8 10 1.8 10z"/><circle cx="10" cy="10" r="2.6"/></svg>',
    "logo": '<svg viewBox="0 0 16 16"><rect width="16" height="16" rx="3" fill="#13305e"/><g fill="#9cc5ff"><rect x="3" y="3" width="2" height="2"/><rect x="7" y="3" width="2" height="2"/><rect x="11" y="3" width="2" height="2"/><rect x="5" y="7" width="2" height="2"/><rect x="9" y="7" width="2" height="2"/><rect x="3" y="11" width="2" height="2"/><rect x="7" y="11" width="2" height="2"/><rect x="11" y="11" width="2" height="2"/></g></svg>',
}


def pixmap(name, size=20, color="#d6d6d6", ratio=2.0):
    svg = SVG[name].replace("{c}", color)
    r = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    r.render(p, QRectF(0, 0, size * ratio, size * ratio))
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name, size=20):
    ic = QIcon()
    ic.addPixmap(pixmap(name, size, "#d6d6d6"), QIcon.Normal, QIcon.Off)
    ic.addPixmap(pixmap(name, size, "#ffffff"), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, size, "#6e6e6e"), QIcon.Disabled)
    return ic
