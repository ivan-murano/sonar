"""Controllo dell'installazione: Sonar.exe --selftest (scrive il risultato su stdout e in selftest.txt)."""
from __future__ import annotations

import sys
import traceback


def run() -> int:
    from . import __version__, config
    lines, ok = [f'Sonar {__version__}', f'Python {sys.version.split()[0]}', f'modelli: {config.models_dir()}'], True

    def check(label, function):
        nonlocal ok
        try:
            detail = function()
            lines.append(f'OK   {label}{": " + str(detail) if detail else ""}')
        except Exception as exc:
            ok = False
            lines.append(f'ERR  {label}: {type(exc).__name__}: {exc}')
            lines.append(traceback.format_exc())

    def gdal():
        import pyogrio
        drivers = pyogrio.list_drivers()
        missing = [d for d in ('GPKG', 'OpenFileGDB') if 'w' not in drivers.get(d, '')]
        if missing:
            raise RuntimeError(f'driver senza scrittura: {missing}')
        return f'GDAL {pyogrio.__gdal_version_string__}'

    def libraries():
        import geopandas, h3, matplotlib, osmium, overturemaps, pyarrow, rasterio, requests, shapely, sklearn  # noqa: F401
        return f'scikit-learn {sklearn.__version__}, geopandas {geopandas.__version__}'

    def model():
        from .model_api import default_model
        m = default_model()
        m.entrypoint()
        code = None
        try:
            module = sys.modules[[k for k in sys.modules if k.startswith(f'sonar_model_{m.id}')][0]]
            if hasattr(module, 'code_root'):
                code = module.code_root(m.folder)
        except Exception as exc:
            raise RuntimeError(f'codice del modello: {exc}') from exc
        return f'{m.id} {m.version}' + (f', codice in {code}' if code else '')

    def qt():
        import PySide6
        return f'PySide6 {PySide6.__version__}'

    def network():
        from . import net
        bundle = net.ca_bundle()
        data = net.get_json('https://gisco-services.ec.europa.eu/id/lau',
                            params={'x': 14.25, 'y': 40.85, 'proj': 4326, 'year': 2024, 'format': 'geojson', 'geometry': 'no'}, timeout=(15, 30))
        name = (data.get('features') or [{}])[0].get('properties', {}).get('lau_name')
        return f'certificati {bundle}; GISCO risponde ({name})'

    check('GDAL e formati', gdal)
    check('librerie geografiche', libraries)
    check('modello', model)
    check('Qt', qt)
    if '--offline' not in sys.argv:
        check('rete (HTTPS)', network)
    lines.append('ESITO: OK' if ok else 'ESITO: ERRORI')
    text = '\n'.join(lines)
    print(text, flush=True)
    try:
        (config.install_dir() / 'selftest.txt').write_text(text, encoding='utf-8')
    except OSError:
        pass
    return 0 if ok else 1
