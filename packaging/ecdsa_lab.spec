# PyInstaller recipe for ECDSA Lab (owner: P2).
#
#   pip install -e ".[package]"
#   pyinstaller packaging/ecdsa_lab.spec --noconfirm
#
# Result: dist/ECDSA-Lab/  (a folder with the ECDSA-Lab executable; zip it to hand it in).
# Build on the operating system you want to run on - PyInstaller does not cross-compile.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))  # so collect_submodules finds ecdsa_edu even if it is not pip-installed

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    # The Theory pages are data files, not Python modules.
    datas=[(str(ROOT / "ecdsa_edu" / "gui" / "theory" / "pages"), "ecdsa_edu/gui/theory/pages")],
    # The main window imports the tabs by name at run time (importlib), which
    # PyInstaller cannot see - so list every module of the package explicitly.
    hiddenimports=collect_submodules("ecdsa_edu") + ["matplotlib.backends.backend_qtagg"],
    # Test-only reference libraries and unused GUI toolkits stay out of the build.
    excludes=["ecdsa", "cryptography", "pytest", "pytestqt", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ECDSA-Lab",
    console=False,  # GUI app: no terminal window
)
coll = COLLECT(exe, a.binaries, a.datas, name="ECDSA-Lab")
