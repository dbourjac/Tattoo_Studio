import sys
import traceback
import json
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox

from ui.styles.themes import apply_theme

SETTINGS = Path(__file__).parent / "settings.json"


def install_qt_exception_hook() -> None:
    """
    Evita que la app se cierre en excepciones no capturadas.
    Muestra un QMessageBox con el traceback y también lo imprime en consola.
    """
    def _excepthook(exc_type, exc, tb):
        err = "".join(traceback.format_exception(exc_type, exc, tb))
        print(err)
        try:
            QMessageBox.critical(None, "Error no capturado", err)
        finally:
            # No matar la app automáticamente.
            pass

    sys.excepthook = _excepthook


def load_qss(app: QApplication) -> None:
    """Carga un QSS adicional si existe (opcional)."""
    theme_path = Path(__file__).parent / "ui" / "styles" / "theme.qss"
    if theme_path.exists():
        qss = theme_path.read_text(encoding="utf-8")
        app.setStyleSheet(qss)


def load_theme_preference() -> str:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "light")
        except Exception:
            pass
    return "light"


def main():
    install_qt_exception_hook()

    app = QApplication(sys.argv)

    # Tema
    mode = load_theme_preference()
    apply_theme(app, mode)
    load_qss(app)

    # Crea la ventana principal (ésta abre el LoginDialog en su __init__)
    from ui.main_window import MainWindow
    from services.contracts import get_current_user

    w = MainWindow()

    # Si el usuario canceló el login, MainWindow cierra y no hay usuario actual → salimos.
    if not get_current_user():
        sys.exit(0)

    # Si hay sesión válida, mostramos la app.
    w.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
