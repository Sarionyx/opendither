"""Dark pro-app theme (same palette as the web app)."""
from PySide6.QtGui import QColor, QPalette

C = {
    "frame": "#1f1f1f", "bar": "#2b2b2b", "panel": "#323232", "panel2": "#2b2b2b", "raised": "#3a3a3a",
    "hover": "#444444", "input": "#1e1e1e", "pasteboard": "#1b1b1b", "line": "#161616", "line_soft": "#404040",
    "text": "#d6d6d6", "dim": "#9b9b9b", "faint": "#6e6e6e", "accent": "#2d7ff9", "accent_hi": "#4b93ff",
}


def palette():
    p = QPalette()
    roles = {
        QPalette.Window: C["panel"], QPalette.WindowText: C["text"], QPalette.Base: C["input"],
        QPalette.AlternateBase: C["panel2"], QPalette.ToolTipBase: "#111111", QPalette.ToolTipText: C["text"],
        QPalette.Text: C["text"], QPalette.Button: C["raised"], QPalette.ButtonText: C["text"],
        QPalette.BrightText: "#ffffff", QPalette.Highlight: C["accent"], QPalette.HighlightedText: "#ffffff",
        QPalette.Link: C["accent_hi"], QPalette.PlaceholderText: C["faint"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(C["faint"]))
    return p


QSS = """
* { font-family: "Segoe UI", "Helvetica Neue", Arial; font-size: 9pt; color: %(text)s; }
QMainWindow, QMainWindow::separator { background: %(frame)s; }
QMainWindow::separator { width: 2px; height: 2px; }
QToolTip { background: #111; color: %(text)s; border: 1px solid #444; padding: 4px 6px; }

QMenuBar { background: %(frame)s; border-bottom: 1px solid %(line)s; padding: 2px 4px; }
QMenuBar::item { padding: 4px 9px; border-radius: 3px; background: transparent; }
QMenuBar::item:selected, QMenuBar::item:pressed { background: %(raised)s; }
QMenu { background: %(panel)s; border: 1px solid %(line)s; padding: 4px; }
QMenu::item { padding: 5px 28px 5px 12px; border-radius: 3px; }
QMenu::item:selected { background: %(accent)s; color: #fff; }
QMenu::item:disabled { color: %(faint)s; }
QMenu::separator { height: 1px; background: %(line_soft)s; margin: 4px 2px; }

QToolBar { background: %(bar)s; border: 0; spacing: 6px; }
QToolBar#options { border-bottom: 1px solid %(line)s; padding: 4px 8px; }
QToolBar#tools { border-right: 1px solid %(line)s; padding: 6px 4px; }
QToolBar::separator { background: %(line_soft)s; width: 1px; height: 1px; margin: 4px; }
QToolBar#tools QToolButton { width: 28px; height: 28px; border-radius: 3px; padding: 0; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 3px 8px; }
QToolButton:hover { background: %(raised)s; }
QToolButton:checked { background: #4a4a4a; border-color: #5c5c5c; }

QPushButton { background: %(raised)s; border: 1px solid #555; border-radius: 4px; padding: 3px 12px; min-height: 16px; }
QPushButton:hover { background: %(hover)s; border-color: #666; }
QPushButton:pressed { background: #2f2f2f; }
QPushButton:disabled { color: %(faint)s; border-color: #444; }
QPushButton[primary="true"] { background: %(accent)s; border-color: %(accent)s; color: #fff; font-weight: 600; }
QPushButton[primary="true"]:hover { background: %(accent_hi)s; border-color: %(accent_hi)s; }
QPushButton[small="true"] { padding: 1px 8px; font-size: 8pt; }
QPushButton[ghost="true"] { background: transparent; border-color: transparent; }
QPushButton[ghost="true"]:hover { background: %(raised)s; border-color: #555; }
QPushButton[seg="true"] { background: %(input)s; border: 1px solid #4a4a4a; border-radius: 0; color: %(dim)s; padding: 2px 6px; }
QPushButton[seg="true"]:checked { background: #4a4a4a; color: #fff; }
QPushButton[segfirst="true"] { border-top-left-radius: 3px; border-bottom-left-radius: 3px; }
QPushButton[seglast="true"] { border-top-right-radius: 3px; border-bottom-right-radius: 3px; border-left: 0; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
  background: %(input)s; border: 1px solid #4a4a4a; border-radius: 3px; padding: 2px 5px; selection-background-color: %(accent)s;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: %(accent)s; }
QSpinBox, QDoubleSpinBox { min-height: 16px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0; border: 0; }
QComboBox { padding-right: 18px; min-height: 16px; }
QComboBox::drop-down { border: 0; width: 18px; }
QComboBox::down-arrow { image: url(%(assets)s/arrow-down.svg); width: 9px; height: 6px; margin-right: 6px; }
QComboBox::down-arrow:disabled { image: none; }
QComboBox QAbstractItemView { background: %(panel)s; border: 1px solid %(line)s; selection-background-color: %(accent)s; outline: 0; padding: 2px; }
QPlainTextEdit { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8pt; color: #cfd8e6; }

QSlider::groove:horizontal { height: 2px; background: #4d4d4d; border-radius: 1px; }
QSlider::sub-page:horizontal { background: #8a8a8a; border-radius: 1px; }
QSlider::handle:horizontal { width: 10px; height: 10px; margin: -5px 0; border-radius: 6px; background: #e4e4e4; border: 2px solid %(panel)s; }
QSlider::handle:horizontal:hover { background: #fff; }
QSlider:disabled { }

QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 12px; height: 12px; border: 1px solid #777; border-radius: 2px; background: %(input)s; }
QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; image: url(%(assets)s/check.svg); }

QDockWidget { titlebar-close-icon: none; titlebar-normal-icon: none; }
QDockWidget::title { background: %(panel2)s; padding: 5px 10px; border-bottom: 1px solid %(line)s; font-weight: 600; }

QTabWidget::pane { border: 0; background: %(panel)s; top: -1px; }
QTabBar { background: %(panel2)s; }
QTabBar::tab { background: %(panel2)s; color: %(dim)s; padding: 5px 12px; border-right: 1px solid %(line)s; border-bottom: 1px solid %(line)s; }
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { background: %(panel)s; color: %(text)s; font-weight: 600; border-bottom-color: %(panel)s; }
QTabBar#docTabs::tab { padding: 4px 10px 4px 12px; max-width: 420px; }
QTabBar#docTabs::tab:selected { border-top: 2px solid %(accent)s; background: %(panel)s; font-weight: 400; }

QScrollArea { border: 0; background: %(panel)s; }
QScrollArea > QWidget > QWidget { background: %(panel)s; }
QScrollBar:vertical { background: %(panel)s; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #4a4a4a; border-radius: 4px; min-height: 30px; margin: 2px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { height: 0; }

QStatusBar { background: %(bar)s; border-top: 1px solid %(line)s; color: %(dim)s; }
QStatusBar::item { border: 0; }
QStatusBar QLabel { color: %(dim)s; padding: 0 8px; border-right: 1px solid %(line_soft)s; font-size: 8pt; }

#sectionHead { background: transparent; border: 0; text-align: left; font-weight: 600; padding: 6px 8px; }
#sectionHead:hover { background: #383838; }
#section { border-bottom: 1px solid %(line)s; }
#fieldLabel { color: %(dim)s; }
#fieldLabel[scrub="true"]:hover { color: %(text)s; }
#hint { color: %(dim)s; }
#swatchBox { background: %(input)s; border: 1px solid #4a4a4a; border-radius: 3px; }
#pasteboard { background: %(pasteboard)s; }
"""


def stylesheet(assets_dir: str) -> str:
    return QSS % dict(C, assets=str(assets_dir).replace("\\", "/"))
