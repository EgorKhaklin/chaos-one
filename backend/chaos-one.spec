# PyInstaller spec for the Chaos One backend launcher.
#
# Builds a single-file (onefile) executable that boots the FastAPI
# dashboard and opens the browser. macOS picks up the .app bundle from
# the BUNDLE() call at the bottom; Linux/Windows get the binary in dist/.
#
# Usage:
#   make package
#   ./dist/chaos-one          (Linux / macOS console)
#   open dist/Chaos\ One.app  (macOS GUI bundle)
#   dist\chaos-one.exe        (Windows)

# ruff: noqa
# mypy: ignore-errors

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

block_cipher = None

hidden_imports = []
hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("fastapi")
hidden_imports += collect_submodules("starlette")
hidden_imports += collect_submodules("chaos_backend")
hidden_imports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
    "python_multipart",
]

datas = []
datas += collect_data_files("uvicorn")
datas += collect_data_files("fastapi")
datas += collect_data_files("starlette")

a = Analysis(
    ["src/chaos_backend/launcher.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="chaos-one",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name="Chaos One.app",
    icon=None,
    bundle_identifier="com.egorkhaklin.chaos-one",
    info_plist={
        "CFBundleName": "Chaos One",
        "CFBundleDisplayName": "Chaos One",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSBackgroundOnly": False,
    },
)
