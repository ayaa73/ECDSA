"""Capture the application pages for visual review with Qt's offscreen plugin."""
from pathlib import Path
import re
from PySide6.QtWidgets import QApplication
from ecdsa_edu.gui.app import apply_theme
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.main_window import MainWindow

app = QApplication([])
apply_theme(app)
window = MainWindow(AppState())
window.show()
destination = Path("docs/screenshots")
destination.mkdir(parents=True, exist_ok=True)
for width, height in ((1440, 900), (1024, 700)):
    window.resize(width, height)
    for title in window.pages:
        window.show_page(title)
        app.processEvents()
        name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        window.grab().save(str(destination / f"{name}-{width}x{height}.png"))
window.close()
