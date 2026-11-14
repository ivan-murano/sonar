"""Consegna: cartelle con nomi nella lingua scelta, GPKG stilizzati, File Geodatabase + .lyrx, PNG, testi."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from ..i18n import filename, folder, pick, t
from . import maps, styles

GPKG_STYLE_TABLE = """CREATE TABLE IF NOT EXISTS layer_styles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT(256), f_table_schema TEXT(256), f_table_name TEXT(256),
    f_geometry_column TEXT(256), styleName TEXT(30), styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN, description TEXT,
    owner TEXT(30), ui TEXT(30), update_time DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))"""
NO_DATA = {'it': 'Nessuna stima', 'en': 'No estimate'}


def safe_name(text: str, limit: int = 60) -> str:
    """Nome valido per file e cartelle Windows, leggibile (spazi -> _)."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', str(text)).strip().strip('.')
    text = re.sub(r'\s+', '_', text)
    return (text[:limit].rstrip('_.') or 'Sonar')


def gdb_name(text: str) -> str:
    """Nome di feature class: lettere, cifre e _, inizia con una lettera, max 64."""
    import unicodedata
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    name = re.sub(r'[^A-Za-z0-9_]+', '_', ascii_text).strip('_')
    return (name if name[:1].isalpha() else 'L_' + name)[:64]


def make_root(base: Path, city_name: str) -> Path:
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M')
    root = Path(base) / f'Sonar_{safe_name(city_name)}_{stamp}'
    n = 2
    while root.exists():
        root = Path(base) / f'Sonar_{safe_name(city_name)}_{stamp}_{n}'; n += 1
    root.mkdir(parents=True)
    return root


def _geometry_kind(frame) -> str:
    return 'line' if frame.geom_type.isin(['LineString', 'MultiLineString']).all() else 'polygon'


def add_gpkg_style(path: Path, layer: str, qml: str, sld: str, title: str):
    """Stile predefinito QGIS nella tabella layer_styles, registrata come tabella di attributi come fa QGIS."""
    import pyogrio
    geometry_column = pyogrio.read_info(path, layer=layer).get('geometry_name') or 'geom'
    with sqlite3.connect(path) as con:
        con.execute(GPKG_STYLE_TABLE)
        con.execute('DELETE FROM layer_styles WHERE f_table_name = ?', (layer,))
        con.execute('INSERT INTO layer_styles (f_table_catalog, f_table_schema, f_table_name, f_geometry_column, styleName, styleQML, styleSLD, '
                    'useAsDefault, description, owner, ui) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)',
                    ('', '', layer, geometry_column, layer[:30], qml, sld, title, 'Sonar', ''))
        if not con.execute("SELECT 1 FROM gpkg_contents WHERE table_name = 'layer_styles'").fetchone():
            con.execute("INSERT INTO gpkg_contents (table_name, data_type, identifier, description, last_change) "
                        "VALUES ('layer_styles', 'attributes', 'layer_styles', 'QGIS layer styles', strftime('%Y-%m-%dT%H:%M:%fZ','now'))")


def field_aliases(output: dict, style: dict, language: str) -> dict:
    unit = style.get('unit', '')
    return {spec['field']: f'{pick(style.get("title"), language)} {pick(spec.get("title"), language)} {unit}'.strip() for spec in output['map_fields']}


def export_results(model, outputs: dict, root: Path, city, boundary_path: Path, language: str, report, log) -> dict:
    """outputs: {output_id: GPKG del modello}. report(fraction, message)."""
    import geopandas as gpd
    results = root / folder('results', language)
    gpkg_dir, gdb_dir, maps_dir = results / folder('gpkg', language), results / folder('gdb', language), results / folder('maps', language)
    lyrx_dir = gdb_dir / folder('arcgis_styles', language)
    for d in (gpkg_dir, gdb_dir, maps_dir, lyrx_dir):
        d.mkdir(parents=True, exist_ok=True)
    city_part = safe_name(city.name)
    gdb_path = gdb_dir / f'{city_part}_Sonar.gdb'
    boundary = gpd.read_file(boundary_path)
    model_name = pick(model.manifest['name'], language)
    manifest_outputs = [o for o in model.manifest['outputs'] if o['id'] in outputs]
    steps = sum(len(o['layers']) for o in manifest_outputs) * 3
    done, written = 0, {'gpkg': [], 'gdb': [], 'lyrx': [], 'png': [], 'warnings': []}
    gdb_ok = True
    for output in manifest_outputs:
        style = model.style(output['style'])
        source = Path(outputs[output['id']])
        stem = f'{city_part}_{pick(output["file_stem"], language)}'
        target = gpkg_dir / f'{stem}.gpkg'
        aliases = field_aliases(output, style, language)
        for sidecar in source.parent.glob(f'{source.stem}*.json'):
            shutil.copy2(sidecar, gpkg_dir / f'{stem}{sidecar.name[len(source.stem):]}')
        for layer in output['layers']:
            frame = gpd.read_file(source, layer=layer['name'], engine='pyogrio')
            kind = _geometry_kind(frame)
            name = pick(layer.get('export_name') or layer['name'], language)
            title = f'{pick(output.get("title"), language)} · {pick(layer.get("title"), language)}'
            # GeoPackage con stile QGIS predefinito
            report(done / steps, t('ex_gpkg', language, name=f'{target.name} / {name}'))
            frame.to_file(target, layer=name, driver='GPKG', engine='pyogrio')
            add_gpkg_style(target, name, styles.qml(style, output['style_field'], kind, title, aliases),
                           styles.sld(style, output['style_field'], kind, name, title), title)
            done += 1
            # File Geodatabase + layer file ArcGIS Pro
            report(done / steps, t('ex_gdb', language))
            feature_class = gdb_name(f'{output["id"]}_{name}')
            if gdb_ok:
                try:
                    frame.to_file(gdb_path, layer=feature_class, driver='OpenFileGDB', engine='pyogrio')
                    lyrx_path = lyrx_dir / f'{stem}_{name}.lyrx'
                    lyrx_path.write_text(styles.lyrx(style, output['style_field'], kind, title, str(gdb_path), feature_class,
                                                     aliases.get(output['style_field'], output['style_field']), NO_DATA[language]), encoding='utf-8')
                    written['gdb'].append(feature_class); written['lyrx'].append(lyrx_path.name)
                except Exception as exc:  # GDAL senza scrittura FileGDB: la consegna resta valida con GPKG e PNG
                    gdb_ok = False
                    written['warnings'].append(f'File Geodatabase: {exc}')
                    log(f'File Geodatabase non creato: {exc}')
            done += 1
            # PNG
            png = maps_dir / f'{stem}_{name}.png'
            report(done / steps, t('ex_png', language, name=png.name))
            maps.render(frame, boundary, output['map_fields'], style, f'{city.name} — {title}',
                        f'{pick(style.get("title"), language)} · {style.get("unit", "")} · {model_name}', png, language, model_name)
            written['png'].append(png.name)
            done += 1
        written['gpkg'].append(target.name)
    if not gdb_ok and gdb_path.exists():
        shutil.rmtree(gdb_path, ignore_errors=True)
    return written


def write_sources(root: Path, language: str, sources: dict, city, model, extra: dict):
    path = root / filename('sources', language)
    payload = {'city': city.to_json() | {'geometry': '(see boundary file)'}, 'model': {'id': model.id, 'version': model.version,
               'name': pick(model.manifest['name'], language), 'documentation_url': model.manifest.get('documentation_url')},
               'inputs': sources, **extra}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return path
