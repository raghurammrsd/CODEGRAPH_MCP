# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

rich_submodules = collect_submodules('rich')
tree_sitter_datas = collect_data_files('tree_sitter')
tree_sitter_languages_datas = collect_data_files('tree_sitter_languages') if 'tree_sitter_languages' in locals() else []

a = Analysis(
    ['src/codegraph/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=tree_sitter_datas + tree_sitter_languages_datas,
    hiddenimports=rich_submodules + [
        'codegraph',
        'codegraph.cli',
        'codegraph.indexing',
        'codegraph.mcp.server',
        'pydantic',
        'typer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='codegraph',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
