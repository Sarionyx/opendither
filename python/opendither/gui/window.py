"""OpenDither desktop app main window."""
from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QImage, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget, QDoubleSpinBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QSlider, QSpinBox, QTabBar, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from .. import ALGORITHMS, DEFAULTS, ENGINE, KERNELS, PALETTES, __version__, dither, find_palette, normalize_settings
from ..core import resolve_palette, to_hex
from . import icons
from .canvas import Canvas, Navigator
from .widgets import Section, Segmented, SliderField, SwatchBar, field_label

TOOL_NAMES = {"hand": "Hand Tool", "zoom": "Zoom Tool", "compare": "Compare Tool"}
ALGO_NAMES = {a["id"]: a["name"] for a in ALGORITHMS}
PROXY_PIXELS = 500_000  # preview size limit when numba is not installed (~1 s per render)
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"


def np_to_pixmap(a):
    h, w = a.shape[:2]
    a = np.ascontiguousarray(a)
    return QPixmap.fromImage(QImage(a.data, w, h, w * 4, QImage.Format_RGBA8888).copy())


def qimage_to_np(img):
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine())[:, : w * 4]
    return arr.reshape(h, w, 4).copy()


class SwatchStack(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(30, 30)
        self.fg, self.bg = "#000000", "#ffffff"
        self.setToolTip("First and last palette colors")

    def set_colors(self, fg, bg):
        self.fg, self.bg = fg, bg
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        for x, y, c in ((11, 10, self.bg), (3, 2, self.fg)):
            p.fillRect(x - 1, y - 1, 19, 19, QColor("#000"))
            p.fillRect(x, y, 17, 17, QColor("#dddddd"))
            p.fillRect(x + 1, y + 1, 15, 15, QColor(c))


class MainWindow(QMainWindow):
    renderDone = Signal(int, object)

    def __init__(self):
        super().__init__()
        self.setWindowIcon(icons.icon("logo", 32))
        self.settings = dict(DEFAULTS)
        self.preset_id = "1-bit"
        self.colors = list(find_palette("1-bit")["colors"])
        self.extracted = None
        self.src = None          # full-res RGBA numpy
        self.preview = None      # proxy RGBA (or same as src)
        self.proxy_factor = 1.0
        self.name = "Untitled"
        self.result = None
        self.export_scale = 1
        self._pool = ThreadPoolExecutor(max_workers=1)
        self._busy = False
        self._pending = False
        self._job = 0
        self._syncing = False
        self.renderDone.connect(self._on_render)

        self.canvas = Canvas()
        self._build_actions()
        self._build_menus()
        self._build_options_bar()
        self._build_tools()
        self._build_central()
        self._build_docks()
        self._build_status()
        self.canvas.viewChanged.connect(self._on_view)
        self.canvas.fileDropped.connect(self.open_path)

        self.resize(1360, 860)
        self._restore()
        self.set_tool("hand")
        self.sync()

    # ================================================================ building
    def _act(self, text, slot, shortcut=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcuts([QKeySequence(s) for s in (shortcut if isinstance(shortcut, list) else [shortcut])])
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        self.addAction(a)
        return a

    def _build_actions(self):
        self.a_open = self._act("Open…", self.open_dialog, "Ctrl+O")
        self.a_sample = self._act("Open Sample Image", self.open_sample)
        self.a_export = self._act("Export Image…", self.export_dialog, ["Ctrl+S", "Ctrl+Shift+E"])
        self.a_import = self._act("Import Recipe…", self.import_recipe)
        self.a_save_recipe = self._act("Save Recipe…", self.save_recipe)
        self.a_close = self._act("Close", self.close_doc, "Ctrl+W")
        self.a_quit = self._act("Quit", self.close, "Ctrl+Q")
        self.a_copy = self._act("Copy Result", self.copy_result, "Ctrl+C")
        self.a_paste = self._act("Paste Image", self.paste_image, "Ctrl+V")
        self.a_reset = self._act("Reset All Settings", self.reset_all)
        self.a_zin = self._act("Zoom In", lambda: self.canvas.step_zoom(1), ["Ctrl+=", "Ctrl++"])
        self.a_zout = self._act("Zoom Out", lambda: self.canvas.step_zoom(-1), "Ctrl+-")
        self.a_fit = self._act("Fit on Screen", self.canvas.fit, "Ctrl+0")
        self.a_100 = self._act("100%", lambda: self.canvas.zoom_at(1.0), "Ctrl+1")
        self.a_compare = self._act("Split Compare", self.toggle_compare, checkable=True)
        self.a_orig = self._act("Show Original", self.toggle_original, checkable=True)
        self.a_shortcuts = self._act("Keyboard Shortcuts", self.show_shortcuts, "F1")
        self.a_about = self._act("About OpenDither", self.show_about)

        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        for tool, key in (("hand", "H"), ("zoom", "Z"), ("compare", "C")):
            a = QAction(icons.icon(tool), f"{TOOL_NAMES[tool]} ({key})", self)
            a.setCheckable(True)
            a.setShortcut(QKeySequence(key))
            a.triggered.connect(lambda _=False, t=tool: self.set_tool(t, from_key=True))
            self.tool_group.addAction(a)
            self.tool_actions[tool] = a
        self.a_orig.setIcon(icons.icon("original"))
        self.a_orig.setToolTip("Show original (hold \\ on the canvas)")

    def _build_menus(self):
        mb = self.menuBar()
        f = mb.addMenu("&File")
        for a in (self.a_open, self.a_sample, None, self.a_export, None, self.a_import, self.a_save_recipe, None,
                  self.a_close, self.a_quit):
            f.addSeparator() if a is None else f.addAction(a)
        e = mb.addMenu("&Edit")
        for a in (self.a_copy, self.a_paste, None, self.a_reset):
            e.addSeparator() if a is None else e.addAction(a)
        v = mb.addMenu("&View")
        for a in (self.a_zin, self.a_zout, self.a_fit, self.a_100, None, self.a_compare, self.a_orig):
            v.addSeparator() if a is None else v.addAction(a)
        self.view_menu = v
        h = mb.addMenu("&Help")
        h.addAction(self.a_shortcuts)
        h.addAction(self.a_about)

    def _build_options_bar(self):
        tb = QToolBar("Options")
        tb.setObjectName("options")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.tool_label = QLabel()
        tb.addWidget(self.tool_label)
        tb.addSeparator()
        for text, slot in (("Fit Screen", self.canvas.fit), ("100%", lambda: self.canvas.zoom_at(1.0))):
            b = QPushButton(text)
            b.setProperty("ghost", True)
            b.clicked.connect(slot)
            tb.addWidget(b)
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(3.125, 6400)
        self.zoom_spin.setDecimals(1)
        self.zoom_spin.setSuffix(" %")
        self.zoom_spin.setFixedWidth(70)
        self.zoom_spin.setKeyboardTracking(False)
        self.zoom_spin.valueChanged.connect(lambda v: self.canvas.zoom_at(v / 100))
        tb.addWidget(self.zoom_spin)
        tb.addSeparator()
        self.compare_check = QCheckBox("Split compare")
        self.compare_check.toggled.connect(self.set_compare)
        tb.addWidget(self.compare_check)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.busy_label = QLabel("◌ Rendering…")
        self.busy_label.setObjectName("hint")
        self.busy_label.setVisible(False)
        tb.addWidget(self.busy_label)
        b_open = QPushButton("Open")
        b_open.clicked.connect(self.open_dialog)
        tb.addWidget(b_open)
        b_exp = QPushButton("Export")
        b_exp.setProperty("primary", True)
        b_exp.clicked.connect(self.export_dialog)
        tb.addWidget(b_exp)

    def _build_tools(self):
        tb = QToolBar("Tools")
        tb.setObjectName("tools")
        tb.setMovable(False)
        tb.setOrientation(Qt.Vertical)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.LeftToolBarArea, tb)
        for a in self.tool_actions.values():
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.a_orig)
        self.swatch_stack = SwatchStack()
        tb.addWidget(self.swatch_stack)

    def _build_central(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.doc_tabs = QTabBar()
        self.doc_tabs.setObjectName("docTabs")
        self.doc_tabs.setTabsClosable(True)
        self.doc_tabs.setDrawBase(False)
        self.doc_tabs.setExpanding(False)
        self.doc_tabs.setElideMode(Qt.ElideRight)
        self.doc_tabs.addTab("Untitled")
        self.doc_tabs.tabCloseRequested.connect(lambda _i: self.close_doc())
        self.doc_tabs.setVisible(False)
        lay.addWidget(self.doc_tabs)
        lay.addWidget(self.canvas, 1)
        self.setCentralWidget(w)

    def _dock(self, title, widget, area=Qt.RightDockWidgetArea):
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetClosable)
        d.setTitleBarWidget(QWidget())  # tabs act as the title, like Adobe panel groups
        self.addDockWidget(area, d)
        return d

    def _build_docks(self):
        # ---- Properties / Recipe
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_properties(), "Properties")
        tabs.addTab(self._build_recipe_tab(), "Recipe")
        tabs.setMinimumWidth(310)
        self.props_dock = self._dock("Properties", tabs)
        # ---- Navigator
        nav_tabs = QTabWidget()
        nav_tabs.setDocumentMode(True)
        nav = QWidget()
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(8, 8, 8, 8)
        self.navigator = Navigator(self.canvas)
        nl.addWidget(self.navigator, 1)
        row = QHBoxLayout()
        b_out, b_in = QPushButton("−"), QPushButton("+")
        for b in (b_out, b_in):
            b.setProperty("ghost", True)
            b.setFixedWidth(26)
        b_out.clicked.connect(lambda: self.canvas.step_zoom(-1))
        b_in.clicked.connect(lambda: self.canvas.step_zoom(1))
        self.nav_zoom = QSlider(Qt.Horizontal)
        self.nav_zoom.setRange(0, 1000)
        self.nav_zoom.valueChanged.connect(self._nav_zoom)
        row.addWidget(b_out)
        row.addWidget(self.nav_zoom, 1)
        row.addWidget(b_in)
        nl.addLayout(row)
        nav_tabs.addTab(nav, "Navigator")
        nav_tabs.setFixedHeight(230)
        self.nav_dock = self._dock("Navigator", nav_tabs)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.props_dock.toggleViewAction())
        self.view_menu.addAction(self.nav_dock.toggleViewAction())

    def _build_properties(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- Dither
        s = Section("Dither")
        self.algo_combo = QComboBox()
        model = self.algo_combo.model()
        group = None
        for a in ALGORITHMS:
            if a["group"] != group:
                group = a["group"]
                self.algo_combo.addItem(group.upper())
                item = model.item(self.algo_combo.count() - 1)
                item.setEnabled(False)
                f = QFont(item.font())
                f.setPointSizeF(7.5)
                f.setBold(True)
                item.setFont(f)
            self.algo_combo.addItem("   " + a["name"], a["id"])
        self.algo_combo.currentIndexChanged.connect(
            lambda i: self.set("algorithm", self.algo_combo.itemData(i)) if self.algo_combo.itemData(i) else None)
        s.add_row("Algorithm", self.algo_combo)
        self.f_strength = SliderField("Diffusion %", 0, 200, 1, 0, 100)
        self.f_strength.valueChanged.connect(lambda v: self.set("strength", v / 100))
        s.add_row(None, self.f_strength)
        self.serp = QCheckBox("Serpentine scan")
        self.serp.toggled.connect(lambda on: self.set("serpentine", on))
        self.serp_label = field_label("")
        s.add_row(self.serp_label, self.serp)
        seed_w = QWidget()
        sl = QHBoxLayout(seed_w)
        sl.setContentsMargins(0, 0, 0, 0)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-2_000_000_000, 2_000_000_000)
        self.seed_spin.setKeyboardTracking(False)
        self.seed_spin.valueChanged.connect(lambda v: self.set("seed", v))
        shuffle = QPushButton("Shuffle")
        shuffle.setProperty("small", True)
        shuffle.clicked.connect(lambda: self.set("seed", random.randint(0, 999_999)))
        sl.addWidget(self.seed_spin, 1)
        sl.addWidget(shuffle)
        self.seed_label = field_label("Seed")
        s.add_row(self.seed_label, seed_w)
        self.seed_w = seed_w
        v.addWidget(s)

        # ---- Adjustments
        reset = QPushButton("Reset")
        reset.setProperty("ghost", True)
        reset.setProperty("small", True)
        reset.clicked.connect(self.reset_adjustments)
        s = Section("Adjustments", reset)
        self.f_bri = SliderField("Brightness", -100, 100, 1, 0, 0)
        self.f_con = SliderField("Contrast", -100, 100, 1, 0, 0)
        self.f_sat = SliderField("Saturation", -100, 100, 1, 0, 0)
        self.f_gam = SliderField("Gamma", 0.1, 5, 0.01, 2, 1)
        for f, key in ((self.f_bri, "brightness"), (self.f_con, "contrast"), (self.f_sat, "saturation"), (self.f_gam, "gamma")):
            f.valueChanged.connect(lambda val, k=key: self.set(k, val))
            s.add_row(None, f)
        self.inv = QCheckBox("Invert")
        self.inv.toggled.connect(lambda on: self.set("invert", on))
        s.add_row("", self.inv)
        v.addWidget(s)

        # ---- Color
        s = Section("Color")
        self.mode_seg = Segmented([("luminance", "Luminance", "Map brightness onto the palette (duotone style)"),
                                   ("rgb", "RGB", "Match full colors against the palette")])
        self.mode_seg.changed.connect(lambda m: self.set("colorMode", m))
        s.add_row("Mode", self.mode_seg)
        self.pal_combo = QComboBox()
        for p in PALETTES:
            self.pal_combo.addItem(f"{p['name']}  ({len(p['colors'])})", p["id"])
        self.pal_combo.addItem("Custom", "__custom")
        self.pal_combo.activated.connect(self._palette_chosen)
        self.pal_label = field_label("Palette")
        s.add_row(self.pal_label, self.pal_combo)
        self.swatches = SwatchBar()
        self.swatches.edited.connect(self._palette_edited)
        s.add_row(None, self.swatches)
        btns = QWidget()
        bl = QHBoxLayout(btns)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addStretch(1)
        self.keep_btn = QPushButton("Keep Extracted")
        self.keep_btn.setProperty("small", True)
        self.keep_btn.clicked.connect(self.keep_extracted)
        hex_btn = QPushButton("Edit Hex…")
        hex_btn.setProperty("small", True)
        hex_btn.clicked.connect(self.edit_hex)
        bl.addWidget(self.keep_btn)
        bl.addWidget(hex_btn)
        s.add_row(None, btns)
        self.f_adapt = SliderField("Adaptive", 0, 64, 1, 0, 0)
        self.f_adapt.valueChanged.connect(lambda val: self.set("adaptive", 0 if val < 2 else int(val)))
        s.add_row(None, self.f_adapt)
        v.addWidget(s)

        # ---- Output
        s = Section("Output")
        self.f_scale = SliderField("Pixel Size", 1, 32, 1, 0, 1)
        self.f_scale.valueChanged.connect(lambda val: self.set("scale", int(val)))
        s.add_row(None, self.f_scale)
        self.exp_combo = QComboBox()
        for k in (1, 2, 3, 4, 6, 8):
            self.exp_combo.addItem(f"{k}×", k)
        self.exp_combo.currentIndexChanged.connect(lambda i: self._set_export_scale(self.exp_combo.itemData(i)))
        s.add_row("Export Scale", self.exp_combo)
        v.addWidget(s)

        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _build_recipe_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        hint = QLabel("A recipe is every setting as JSON. It works the same in this app, the web app, "
                      "the CLI and the &lt;open-dither&gt; web component.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.recipe_edit = QPlainTextEdit()
        lay.addWidget(self.recipe_edit, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        for text, slot in (("Apply", self.apply_recipe_text), ("Copy", self.copy_recipe), ("Save…", self.save_recipe)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)
        lab = QLabel("Command line equivalent")
        lab.setObjectName("hint")
        lay.addWidget(lab)
        self.cli_edit = QLineEdit()
        self.cli_edit.setReadOnly(True)
        lay.addWidget(self.cli_edit)
        return w

    def _build_status(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.st = {k: QLabel() for k in ("zoom", "size", "algo", "palette", "time", "engine")}
        for k in ("zoom", "size", "algo"):
            sb.addWidget(self.st[k])
        for k in ("palette", "time", "engine"):
            sb.addPermanentWidget(self.st[k])

    # ================================================================ state
    def recipe(self):
        r = dict(self.settings)
        r["palette"] = self.preset_id or list(self.colors)
        return r

    def set(self, key, value):
        if self._syncing:
            return
        self.settings[key] = value
        self.sync()
        self.request_render()

    def sync(self):
        """Push state into every widget without re-triggering signals."""
        self._syncing = True
        s = self.settings
        try:
            i = self.algo_combo.findData(s["algorithm"])
            self.algo_combo.setCurrentIndex(i)
            diffusion = s["algorithm"] in KERNELS
            self.f_strength.set_label("Diffusion %" if diffusion else "Spread %")
            self.f_strength.set_value(s["strength"] * 100)
            self.f_strength.setEnabled(s["algorithm"] != "threshold")
            self.serp.setChecked(bool(s["serpentine"]))
            self.serp.setVisible(diffusion)
            self.serp_label.setVisible(diffusion)
            self.seed_spin.setValue(int(s["seed"]))
            self.seed_w.setVisible(s["algorithm"] == "random")
            self.seed_label.setVisible(s["algorithm"] == "random")
            self.f_bri.set_value(s["brightness"])
            self.f_con.set_value(s["contrast"])
            self.f_sat.set_value(s["saturation"])
            self.f_sat.setEnabled(s["colorMode"] == "rgb")
            self.f_gam.set_value(s["gamma"])
            self.inv.setChecked(bool(s["invert"]))
            self.mode_seg.set_value(s["colorMode"])
            self.pal_combo.setCurrentIndex(self.pal_combo.findData(self.preset_id or "__custom"))
            self.pal_combo.setEnabled(not s["adaptive"])
            self.f_adapt.set_value(s["adaptive"])
            self.f_adapt.set_label("Adaptive" if s["adaptive"] else "Adaptive (off)")
            self.keep_btn.setVisible(bool(s["adaptive"]))
            self.f_scale.set_value(s["scale"])
            self._render_swatches()
            if not self.recipe_edit.hasFocus():
                self.recipe_edit.setPlainText(json.dumps(self.recipe(), indent=2))
            self.cli_edit.setText(self._cli_command())
            self._update_status()
        finally:
            self._syncing = False

    def _render_swatches(self):
        adaptive = bool(self.settings["adaptive"])
        colors = (self.extracted or []) if adaptive else self.colors
        if (getattr(self, "_shown_swatches", None) != (tuple(colors), adaptive)):
            self.swatches.set_colors(colors, locked=adaptive)
            self._shown_swatches = (tuple(colors), adaptive)
        pal = colors or ["#000000", "#ffffff"]
        self.swatch_stack.set_colors(pal[0], pal[-1])

    def _cli_command(self):
        s, parts = self.settings, ["opendither", '"input.jpg"']
        flags = {"algorithm": "-a", "colorMode": "-m", "scale": "--scale", "strength": "--strength", "seed": "--seed",
                 "brightness": "--brightness", "contrast": "--contrast", "saturation": "--saturation",
                 "gamma": "--gamma", "adaptive": "--adaptive"}
        for k, flag in flags.items():
            if k == "algorithm" or s[k] != DEFAULTS[k]:
                val = s[k]
                if isinstance(val, float) and val.is_integer():
                    val = int(val)
                elif isinstance(val, float):
                    val = round(val, 3)
                parts.append(f"{flag} {val}")
        if not s["serpentine"]:
            parts.append("--no-serpentine")
        if s["invert"]:
            parts.append("--invert")
        if not s["adaptive"]:
            parts.append(f'-p "{self.preset_id or ",".join(self.colors)}"')
        if self.export_scale > 1:
            parts.append(f"--export-scale {self.export_scale}")
        return " ".join(parts)

    def _palette_chosen(self, i):
        pid = self.pal_combo.itemData(i)
        if pid == "__custom":
            self.preset_id = None
        else:
            self.preset_id = pid
            self.colors = list(find_palette(pid)["colors"])
        self.sync()
        self.request_render()

    def _palette_edited(self, colors):
        self.colors = colors
        self.preset_id = None
        QTimer.singleShot(0, lambda: (self.sync(), self.request_render()))

    def keep_extracted(self):
        if self.extracted:
            self.colors = list(self.extracted)
            self.preset_id = None
            self.settings["adaptive"] = 0
            self.sync()
            self.request_render()

    def edit_hex(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Palette Colors")
        lay = QVBoxLayout(dlg)
        hint = QLabel("One hex color per line (or comma separated). Paste palettes from any palette site.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        ed = QPlainTextEdit("\n".join(self.colors))
        lay.addWidget(ed)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(340, 360)
        if dlg.exec() == QDialog.Accepted:
            try:
                self.colors = [to_hex(c) for c in resolve_palette(ed.toPlainText())]
            except ValueError as ex:
                QMessageBox.warning(self, "Palette", str(ex))
                return
            self.preset_id = None
            self.settings["adaptive"] = 0
            self.sync()
            self.request_render()

    def reset_adjustments(self):
        for k in ("brightness", "contrast", "saturation", "gamma", "invert"):
            self.settings[k] = DEFAULTS[k]
        self.sync()
        self.request_render()

    def reset_all(self):
        self.apply_recipe(DEFAULTS)
        self.statusBar().showMessage("Settings reset", 2000)

    def apply_recipe(self, obj):
        s = normalize_settings(obj)
        p = s.pop("palette")
        if isinstance(p, str) and find_palette(p):
            self.preset_id, self.colors = p, list(find_palette(p)["colors"])
        else:
            self.preset_id, self.colors = None, [to_hex(c) for c in resolve_palette(p)]
        self.settings = dict(DEFAULTS, **s)
        self.sync()
        self.request_render()

    def _set_export_scale(self, k):
        self.export_scale = k or 1
        self.sync()

    # ================================================================ rendering
    def request_render(self):
        if self.preview is None:
            return
        if self._busy:
            self._pending = True
            return
        self._busy = True
        self._job += 1
        job, img, rec = self._job, self.preview, self.recipe()
        if self.proxy_factor < 1:
            rec["scale"] = max(1, round(rec["scale"] * self.proxy_factor))
        QTimer.singleShot(150, lambda: self.busy_label.setVisible(self._busy))

        def work():
            try:
                res = dither(img, rec)
            except Exception as ex:  # report in the UI rather than crash the worker
                res = ex
            self.renderDone.emit(job, res)

        self._pool.submit(work)

    @Slot(int, object)
    def _on_render(self, job, res):
        self._busy = False
        self.busy_label.setVisible(False)
        if isinstance(res, Exception):
            self.statusBar().showMessage(f"Render failed: {res}", 6000)
        elif self.preview is not None and res.image.shape[:2] == self.preview.shape[:2]:
            self.result = res
            self.extracted = res.palette if self.settings["adaptive"] else None
            pm = np_to_pixmap(res.image)
            self.canvas.set_result(pm)
            self.navigator.set_source(pm)
            self._render_swatches()
            self._update_status()
        if self._pending:
            self._pending = False
            self.request_render()

    def full_result(self):
        """Full-resolution result (re-renders when the preview is a proxy)."""
        if self.src is None:
            return None
        if self.proxy_factor == 1 and self.result is not None:
            return self.result
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.statusBar().showMessage("Rendering full resolution…")
            QApplication.processEvents()
            return dither(self.src, self.recipe())
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()

    # ================================================================ documents
    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", self._last_dir(), IMAGE_FILTER + ";;All files (*)")
        if path:
            self.open_path(path)

    def open_path(self, path):
        p = Path(path)
        if p.suffix.lower() == ".json":
            try:
                self.apply_recipe(json.loads(p.read_text(encoding="utf-8")))
            except Exception as ex:
                QMessageBox.warning(self, "Recipe", f"Could not read recipe:\n{ex}")
            return
        try:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im).convert("RGBA")
                arr = np.asarray(im).copy()
        except Exception as ex:
            QMessageBox.warning(self, "Open Image", f"Could not open {p.name}:\n{ex}")
            return
        QSettings().setValue("lastDir", str(p.parent))
        self.load_array(arr, p.name)

    def open_sample(self):
        from .sample import make_sample
        self.load_array(np.asarray(make_sample().convert("RGBA")).copy(), "sample.png")

    def load_array(self, arr, name):
        h, w = arr.shape[:2]
        if w * h > 100_000_000:
            QMessageBox.warning(self, "Open Image", "Image is too large (max 100 megapixels).")
            return
        self.src = arr
        self.name = name
        self.result = None
        self.proxy_factor = 1.0
        self.preview = arr
        if ENGINE != "numba" and w * h > PROXY_PIXELS:
            k = (PROXY_PIXELS / (w * h)) ** 0.5
            pw, ph = max(1, int(w * k)), max(1, int(h * k))
            self.preview = np.asarray(Image.fromarray(arr, "RGBA").resize((pw, ph), Image.LANCZOS)).copy()
            self.proxy_factor = pw / w
            self.statusBar().showMessage("Install numba for full-resolution previews — showing a fast proxy. "
                                         "Exports are always full resolution.", 8000)
        self.doc_tabs.setVisible(True)
        pm = np_to_pixmap(arr)
        self.canvas.set_original(pm)
        self.navigator.set_source(pm)
        self.sync()
        self.request_render()

    def close_doc(self):
        self.src = self.preview = self.result = None
        self.canvas.clear()
        self.navigator.set_source(None)
        self.doc_tabs.setVisible(False)
        self._update_status()

    def export_dialog(self):
        if self.src is None:
            self.statusBar().showMessage("Open an image first", 3000)
            return
        stem = Path(self.name).stem
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Image", str(Path(self._last_dir()) / f"{stem}-dithered.png"),
            "PNG (*.png);;WebP (*.webp);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tif)")
        if not path:
            return
        res = self.full_result()
        kw = {"lossless": True} if path.lower().endswith(".webp") else {}
        if path.lower().endswith((".jpg", ".jpeg")):
            kw = {"quality": 95}
        try:
            res.save(path, scale=self.export_scale, **kw)
        except Exception as ex:
            QMessageBox.warning(self, "Export", f"Could not save:\n{ex}")
            return
        self.statusBar().showMessage(f"Exported {Path(path).name}", 4000)

    def copy_result(self):
        res = self.full_result()
        if res is None:
            return
        img = res.image
        if self.export_scale > 1:
            img = np.repeat(np.repeat(img, self.export_scale, 0), self.export_scale, 1)
        QApplication.clipboard().setPixmap(np_to_pixmap(img))
        self.statusBar().showMessage("Copied to clipboard", 2500)

    def paste_image(self):
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md.hasImage():
            img = cb.image()
            if not img.isNull():
                self.load_array(qimage_to_np(img), "Pasted image.png")
                return
        if md.hasUrls() and md.urls()[0].isLocalFile():
            self.open_path(md.urls()[0].toLocalFile())
            return
        self.statusBar().showMessage("No image on the clipboard", 2500)

    # ================================================================ recipes
    def import_recipe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Recipe", self._last_dir(), "Recipe (*.json)")
        if path:
            self.open_path(path)

    def save_recipe(self):
        stem = Path(self.name).stem if self.src is not None else "my-look"
        path, _ = QFileDialog.getSaveFileName(self, "Save Recipe", str(Path(self._last_dir()) / f"{stem}.recipe.json"),
                                              "Recipe (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.recipe(), indent=2), encoding="utf-8")
            self.statusBar().showMessage(f"Saved {Path(path).name}", 3000)

    def apply_recipe_text(self):
        try:
            self.apply_recipe(json.loads(self.recipe_edit.toPlainText()))
            self.statusBar().showMessage("Recipe applied", 2000)
        except Exception as ex:
            QMessageBox.warning(self, "Recipe", f"Invalid recipe:\n{ex}")

    def copy_recipe(self):
        QApplication.clipboard().setText(self.recipe_edit.toPlainText())
        self.statusBar().showMessage("Recipe copied", 2000)

    # ================================================================ view & tools
    def set_tool(self, tool, from_key=False):
        if tool == "compare":
            # choosing the compare tool turns the split on; choosing it again toggles the split
            if from_key and self.canvas.tool == "compare":
                self.set_compare(not self.canvas.compare)
            elif not self.canvas.compare:
                self.set_compare(True)
        self.canvas.set_tool(tool)
        self.tool_actions[tool].setChecked(True)
        self.tool_label.setText(f"  {TOOL_NAMES[tool]}")

    def set_compare(self, on):
        self.canvas.compare = bool(on)
        for w in (self.compare_check, self.a_compare):
            w.blockSignals(True)
            w.setChecked(bool(on))
            w.blockSignals(False)
        self.canvas.update()

    def toggle_compare(self):
        self.set_compare(not self.canvas.compare)

    def toggle_original(self):
        self.canvas.show_original = self.a_orig.isChecked()
        self.canvas.update()

    def _nav_zoom(self, v):
        if not self._syncing:
            self.canvas.zoom_at(2 ** (v / 100 - 4))

    def _on_view(self):
        self._syncing = True
        z = self.canvas.zoom
        self.zoom_spin.blockSignals(True)
        self.zoom_spin.setValue(z * 100)
        self.zoom_spin.blockSignals(False)
        self.nav_zoom.blockSignals(True)
        self.nav_zoom.setValue(int(round((np.log2(z) + 4) * 100)))
        self.nav_zoom.blockSignals(False)
        self._syncing = False
        self._update_status()

    def _update_status(self):
        s = self.settings
        has = self.src is not None
        n = s["adaptive"] or len(self.colors)
        z = f"{self.canvas.zoom * 100:.4g}%"
        self.st["zoom"].setText(z if has else "—")
        if has:
            h, w = self.src.shape[:2]
            size = f"{w} × {h} px"
            if self.export_scale > 1:
                size += f"  →  export {w * self.export_scale} × {h * self.export_scale}"
            self.st["size"].setText(size)
        else:
            self.st["size"].setText("No document")
        self.st["algo"].setText(f"{ALGO_NAMES[s['algorithm']]}" + (f" · {s['scale']}px" if s["scale"] > 1 else "")
                                + f" · {'RGB' if s['colorMode'] == 'rgb' else 'Luminance'}")
        self.st["palette"].setText(f"{n} colors" + (" (adaptive)" if s["adaptive"] else ""))
        self.st["time"].setText(f"{self.result.ms:.0f} ms" + (" (proxy)" if self.proxy_factor < 1 else "")
                                if self.result is not None and has else "")
        self.st["engine"].setText(f"engine: {ENGINE}")
        label = f"{self.name} @ {z} ({ALGO_NAMES[s['algorithm']]}, {n} colors)"
        self.doc_tabs.setTabText(0, label)
        self.setWindowTitle(f"{label} — OpenDither" if has else "OpenDither")

    # ================================================================ dialogs
    def show_shortcuts(self):
        rows = [("Open image", "Ctrl+O"), ("Export", "Ctrl+S"), ("Copy result", "Ctrl+C"), ("Paste image", "Ctrl+V"),
                ("Hand tool", "H  (or hold Space)"), ("Zoom tool", "Z  (Alt-click zooms out)"), ("Compare tool", "C"),
                ("Show original", "hold \\ over the canvas"), ("Zoom in / out", "Ctrl + / Ctrl −  or mouse wheel"),
                ("Fit / 100%", "Ctrl+0 / Ctrl+1"), ("Fine-tune a slider", "drag its label, Shift for precision"),
                ("Reset a slider", "double-click its label")]
        html = "<table cellpadding=3>" + "".join(
            f"<tr><td>{a}</td><td style='color:#9b9b9b;padding-left:24px'>{b}</td></tr>" for a, b in rows) + "</table>"
        QMessageBox.information(self, "Keyboard Shortcuts", html)

    def show_about(self):
        QMessageBox.about(self, "About OpenDither",
                          f"<b>OpenDither {__version__}</b><br>Free and open-source dithering.<br><br>"
                          "The same engine ships as a Python library, CLI and desktop app, and as a JavaScript "
                          "library, web app and &lt;open-dither&gt; web component. Recipes are portable between "
                          f"all of them.<br><br>MIT licensed · render engine: {ENGINE}")

    # ================================================================ persistence
    def _last_dir(self):
        return QSettings().value("lastDir", str(Path.home()))

    def _restore(self):
        qs = QSettings()
        geo = qs.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        rec = qs.value("recipe")
        if rec:
            try:
                s = normalize_settings(json.loads(rec))
                p = s.pop("palette")
                if isinstance(p, str) and find_palette(p):
                    self.preset_id, self.colors = p, list(find_palette(p)["colors"])
                else:
                    self.preset_id, self.colors = None, [to_hex(c) for c in resolve_palette(p)]
                self.settings = dict(DEFAULTS, **s)
            except Exception:
                pass

    def closeEvent(self, e):
        qs = QSettings()
        qs.setValue("geometry", self.saveGeometry())
        qs.setValue("recipe", json.dumps(self.recipe()))
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(e)
