# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: Sonar per Windows (cartella dist/Sonar con Sonar.exe). Lanciato da build/BUILD_WINDOWS.cmd.
# I pacchetti modello NON sono dentro l'eseguibile: build/bundle_models.py li copia in dist/Sonar/models,
# così un modello si aggiorna senza ricostruire il software. Le dipendenze Python del modello vengono
# però congelate qui: lo spec legge gli import del codice del modello (SONAR_MODEL_CODE).
import ast
import importlib.util
import json
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
MODEL_CODE = os.environ.get('SONAR_MODEL_CODE')


def model_python_files():
    files = list((ROOT / 'models').glob('*/*.py'))
    for manifest in (ROOT / 'models').glob('*/sonar_model.json'):
        code = json.loads(manifest.read_text(encoding='utf-8')).get('code') or {}
        root = Path(os.environ.get(code.get('env', ''), '') or MODEL_CODE or '')
        if root.is_dir():
            for pattern in code.get('bundle', []):
                files += [p for p in root.glob(pattern) if p.suffix == '.py']
    return files


def third_party_imports(files):
    local = {p.stem for p in files} | {'sonar', 'sonar_app'}
    found = set()
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.split('.')[0] not in local:
                    found.add(name)
    result = []
    for name in sorted(found):
        try:
            if importlib.util.find_spec(name.split('.')[0]) is not None:
                result.append(name)
        except (ImportError, ValueError):
            pass
    return result


hidden = set(collect_submodules('sonar_app'))
hidden |= set(third_party_imports(model_python_files()))
for package in ('holidays', 'rasterio', 'pyogrio', 'osmium', 'h3', 'shapely', 'pyproj', 'overturemaps',
                'sklearn.ensemble._hist_gradient_boosting'):
    hidden |= set(collect_submodules(package, filter=lambda n: '.tests' not in n and '.test_' not in n))
hidden |= {'sklearn.ensemble', 'sklearn.utils._typedefs', 'sklearn.utils._heap', 'sklearn.utils._sorting', 'sklearn.utils._vector_sentinel',
           'sklearn.neighbors._partition_nodes', 'scipy.spatial', 'scipy.sparse.csgraph', 'scipy.special', 'pyarrow.parquet', 'pyarrow.dataset',
           'pyarrow.fs', 'zoneinfo', 'tzdata', 'sqlite3', 'matplotlib.backends.backend_agg', 'PIL.PngImagePlugin', 'PySide6.QtSvg'}

datas = [(str(p), str(p.parent.relative_to(ROOT))) for p in (ROOT / 'sonar_app' / 'assets').rglob('*') if p.is_file()]
datas += [(str(ROOT / name), '.') for name in ('LICENSE.txt', 'AUTHORS.txt', 'THIRD_PARTY_NOTICES.md')]
for package in ('pyogrio', 'rasterio', 'pyproj', 'holidays', 'overturemaps'):   # dati GDAL/PROJ e tabelle
    datas += collect_data_files(package, excludes=['**/tests/**'])

a = Analysis([str(ROOT / 'build' / 'sonar_entry.py')], pathex=[str(ROOT)], binaries=[], datas=datas, hiddenimports=sorted(hidden),
             hookspath=[], hooksconfig={'matplotlib': {'backends': ['Agg']}}, runtime_hooks=[],
             excludes=['tkinter', 'IPython', 'jupyter', 'notebook', 'pytest', 'PySide6.QtWebEngineCore', 'PySide6.QtQuick', 'PySide6.QtQml',
                       'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtCharts', 'PySide6.QtDataVisualization'],
             noarchive=False)
pyz = PYZ(a.pure)
icon = ROOT / 'sonar_app' / 'assets' / 'sonar.ico'
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Sonar', debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(icon) if icon.exists() else None, version=str(ROOT / 'build' / 'version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Sonar')
