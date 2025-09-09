import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication

# Importamos ventanas principales de nuestro paquete ui
from ui.login import LoginWindow
from ui.main_window import MainWindow
import json
from pathlib import Path
from ui.styles.themes import apply_theme
SETTINGS = Path(__file__).parent / "settings.json"
1

def load_qss(app: QApplication):
    """
    Carga el tema global (QSS) para toda la app.
    Así no repetimos estilos en cada ventana.
    """
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

def save_theme_preference(mode: str):
    SETTINGS.write_text(json.dumps({"theme": mode}, indent=2), encoding="utf-8")


def main():
    app = QApplication(sys.argv)
    mode = load_theme_preference()
    apply_theme(app, mode)
    load_qss(app)

    login = LoginWindow()
    mainw = MainWindow()

    # flujo: login -> principal
    login.acceso_solicitado.connect(lambda: (login.hide(), mainw.show()))
    # flujo: panel usuario -> cambiar usuario -> login
    mainw.solicitar_switch_user.connect(lambda: (mainw.hide(), login.show(), mainw.btn_user.setChecked(False)))

    login.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
