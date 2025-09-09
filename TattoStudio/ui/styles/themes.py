from pathlib import Path
from PyQt5.QtWidgets import QApplication

def apply_theme(app: QApplication, mode: str = "light"):
    """Carga el QSS correcto según 'mode'."""
    base = Path(__file__).parent
    fname = "theme_dark.qss" if mode == "dark" else "theme_light.qss"
    qss = (base / fname).read_text(encoding="utf-8")
    app.setStyleSheet(qss)
