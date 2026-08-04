# PyInstaller spec — one file, one window, no console.
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["../homestead/app/__main__.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=["http", "socket", "ssl", "urllib", "email", "xmlrpc"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Homestead",
    console=False,          # it is an app, not a terminal program
    disable_windowed_traceback=False,
    upx=False,
)
