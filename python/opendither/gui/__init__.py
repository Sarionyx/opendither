"""OpenDither desktop app (PySide6). Run with `opendither-gui` or `python -m opendither`."""
import sys
from pathlib import Path


def main(argv=None):
    try:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWidgets import QApplication, QStyleFactory
    except ImportError:
        print("The desktop app needs PySide6:  pip install \"opendither[gui]\"", file=sys.stderr)
        return 1

    from . import theme
    from .window import MainWindow

    QCoreApplication.setOrganizationName("OpenDither")
    QCoreApplication.setApplicationName("OpenDither")
    app = QApplication.instance() or QApplication(sys.argv if argv is None else argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(theme.palette())
    app.setStyleSheet(theme.stylesheet(Path(__file__).parent / "assets"))

    win = MainWindow()
    win.show()
    args = [a for a in (sys.argv[1:] if argv is None else argv[1:]) if not a.startswith("-")]
    if args:
        win.open_path(args[0])
    return app.exec()
