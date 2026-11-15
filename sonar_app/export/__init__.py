"""Consegna: cartelle con nomi nella lingua scelta, GPKG stilizzati, File Geodatabase + .lyrx, PNG, testi."""
from __future__ import annotations

import json
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from datetime import datetime
from pathlib import Path

from ..i18n import filename, folder, pick, t
from . import health, maps, styles

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
    """Stile predefinito QGIS nella tabella layer_styles (vedi add_gpkg_styles)."""
    add_gpkg_styles(path, layer, [(layer, qml, sld, title)])


def add_gpkg_styles(path: Path, layer: str, entries: list[tuple[str, str, str, str]]):
    """Stili QGIS nella tabella layer_styles, registrata come tabella di attributi come fa QGIS; il primo è il predefinito.
    entries: [(nome, qml, sld, descrizione)]."""
    import pyogrio
    geometry_column = pyogrio.read_info(path, layer=layer).get('geometry_name') or 'geom'
    with sqlite3.connect(path) as con:
        con.execute(GPKG_STYLE_TABLE)
        con.execute('DELETE FROM layer_styles WHERE f_table_name = ?', (layer,))
        for i, (name, qml, sld, title) in enumerate(entries):
            con.execute('INSERT INTO layer_styles (f_table_catalog, f_table_schema, f_table_name, f_geometry_column, styleName, styleQML, styleSLD, '
                        'useAsDefault, description, owner, ui) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        ('', '', layer, geometry_column, name[:30], qml, sld, 1 if i == 0 else 0, title, 'Sonar', ''))
        if not con.execute("SELECT 1 FROM gpkg_contents WHERE table_name = 'layer_styles'").fetchone():
            con.execute("INSERT INTO gpkg_contents (table_name, data_type, identifier, description, last_change) "
                        "VALUES ('layer_styles', 'attributes', 'layer_styles', 'QGIS layer styles', strftime('%Y-%m-%dT%H:%M:%fZ','now'))")


def field_aliases(output: dict, style: dict, language: str, indicator_styles: dict | None = None) -> dict:
    unit = style.get('unit', '')
    aliases = {spec['field']: f'{pick(style.get("title"), language)} {pick(spec.get("title"), language)} {unit}'.strip()
               for spec in output['map_fields']}
    for item in (indicator_styles or {}).values():
        aliases[item['field']] = f'{item["label"]} {item.get("unit", "")}'.strip()
    return aliases


def export_results(model, outputs: dict, root: Path, city, boundary_path: Path, language: str, report, log) -> dict:
    """outputs: {output_id: GPKG del modello}. report(fraction, message).

    Se il manifest attiva "indicators", ai layer si aggiungono Lden/Lnight indicativi: diventano lo stile predefinito
    di GPKG e .lyrx e l'unica tavola PNG per output (sintesi feriale/festivo); i campi per fascia restano nei dati."""
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
    cfg = health.config(model.manifest)
    if cfg and not all(health.hourly_fields(o['map_fields']) for o in manifest_outputs):
        log('Indicatori Lden/Lnight non calcolati: map_fields senza "hours" che coprano le 24 ore')
        cfg = None
    layer_count = sum(len(o['layers']) for o in manifest_outputs)
    steps = layer_count * 3 if not cfg else layer_count * 2 + len(manifest_outputs)
    done, written = 0, {'gpkg': [], 'gdb': [], 'lyrx': [], 'png': [], 'warnings': []}
    # 1. lettura dei layer e indicatori
    loaded = []
    for output in manifest_outputs:
        source = Path(outputs[output['id']])
        for layer in output['layers']:
            frame = gpd.read_file(source, layer=layer['name'], engine='pyogrio')
            if cfg:
                health.add_to_frame(frame, output['map_fields'], cfg['items'])
            loaded.append((output, layer, frame))
    indicator_styles = {}
    if cfg:
        base = model.style(manifest_outputs[0]['style']) if manifest_outputs else {}
        indicator_styles = health.styles_for([f for _, _, f in loaded], cfg, base, language)
    # 2. scrittura: GeoPackage, File Geodatabase e tavole PNG sono file indipendenti e procedono insieme
    lock = threading.Lock()
    state = {'done': done, 'gdb_ok': True}

    def step(message):
        with lock:
            report(state['done'] / steps, message)

    def advance():
        with lock:
            state['done'] += 1

    plans = []
    for output in manifest_outputs:
        style = model.style(output['style'])
        source = Path(outputs[output['id']])
        stem = f'{city_part}_{pick(output["file_stem"], language)}'
        aliases = field_aliases(output, style, language, indicator_styles)
        for sidecar in source.parent.glob(f'{source.stem}*.json'):
            shutil.copy2(sidecar, gpkg_dir / f'{stem}{sidecar.name[len(source.stem):]}')
        layers = []
        for out, layer, frame in loaded:
            if out is not output:
                continue
            name = pick(layer.get('export_name') or layer['name'], language)
            layer_title = pick(layer.get('title'), language)
            layers.append({'frame': frame, 'kind': _geometry_kind(frame), 'name': name, 'layer_title': layer_title,
                           'title': f'{pick(output.get("title"), language)} · {layer_title}'})
        plans.append({'output': output, 'style': style, 'stem': stem, 'aliases': aliases, 'target': gpkg_dir / f'{stem}.gpkg', 'layers': layers})

    def write_gpkg():
        names = []
        for plan in plans:
            output, style, aliases, target = plan['output'], plan['style'], plan['aliases'], plan['target']
            for item in plan['layers']:
                frame, kind, name, title = item['frame'], item['kind'], item['name'], item['title']
                step(t('ex_gpkg', language, name=f'{target.name} / {name}'))
                frame.to_file(target, layer=name, driver='GPKG', engine='pyogrio')
                laeq_field = output['style_field']
                laeq_label = f'{aliases.get(laeq_field, laeq_field)}'
                entries = [(pick(st['title'], language), styles.qml(st, st['field'], kind, title, aliases),
                            styles.sld(st, st['field'], kind, name, title), f'{title} · {st["label"]}')
                           for st in indicator_styles.values()]
                entries.append((laeq_label[:30] if entries else name, styles.qml(style, laeq_field, kind, title, aliases),
                                styles.sld(style, laeq_field, kind, name, title), f'{title} · {laeq_label}' if entries else title))
                add_gpkg_styles(target, name, entries)
                advance()
            names.append(target.name)
        return names

    def write_gdb():
        gdb, lyrx = [], []
        for plan in plans:
            output, style, aliases, stem = plan['output'], plan['style'], plan['aliases'], plan['stem']
            for item in plan['layers']:
                frame, kind, name, title = item['frame'], item['kind'], item['name'], item['title']
                step(t('ex_gdb', language))
                feature_class = gdb_name(f'{output["id"]}_{name}')
                if state['gdb_ok']:
                    try:
                        frame.to_file(gdb_path, layer=feature_class, driver='OpenFileGDB', engine='pyogrio')
                        lyrx_path = lyrx_dir / f'{stem}_{name}.lyrx'
                        main = next(iter(indicator_styles.values()), None)
                        laeq_field = output['style_field']
                        lyrx_style, lyrx_field = (main, main['field']) if main else (style, laeq_field)
                        lyrx_path.write_text(styles.lyrx(lyrx_style, lyrx_field, kind, f'{title} · {main["label"]}' if main else title, str(gdb_path),
                                                         feature_class, aliases.get(lyrx_field, lyrx_field), NO_DATA[language]), encoding='utf-8')
                        gdb.append(feature_class); lyrx.append(lyrx_path.name)
                    except Exception as exc:  # GDAL senza scrittura FileGDB: la consegna resta valida con GPKG e PNG
                        state['gdb_ok'] = False
                        with lock:
                            written['warnings'].append(f'File Geodatabase: {exc}')
                            log(f'File Geodatabase non creato: {exc}')
                advance()
        return gdb, lyrx

    def write_png():
        pngs = []
        for plan in plans:
            output, style, stem = plan['output'], plan['style'], plan['stem']
            if cfg:
                sheet = [(item['layer_title'], item['frame']) for item in plan['layers']]
                if sheet:
                    suffix = '_'.join(health.INDICATORS[i]['field'].split('_')[0].capitalize() for i in cfg['items'])
                    png = maps_dir / f'{stem}_{suffix}.png'
                    step(t('ex_png', language, name=png.name))
                    maps.render_indicators(sheet, boundary, list(indicator_styles.values()), f'{city.name} — {pick(output.get("title"), language)}',
                                           png, language, model_name)
                    pngs.append(png.name)
                    advance()
                continue
            for item in plan['layers']:     # PNG per layer (modelli senza indicatori): un riquadro per fascia
                png = maps_dir / f'{stem}_{item["name"]}.png'
                step(t('ex_png', language, name=png.name))
                maps.render(item['frame'], boundary, output['map_fields'], style, f'{city.name} — {item["title"]}',
                            f'{pick(style.get("title"), language)} · {style.get("unit", "")} · {model_name}', png, language, model_name)
                pngs.append(png.name)
                advance()
        return pngs

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_gpkg, f_gdb, f_png = pool.submit(write_gpkg), pool.submit(write_gdb), pool.submit(write_png)
        written['gpkg'] = f_gpkg.result()
        written['gdb'], written['lyrx'] = f_gdb.result()
        written['png'] = f_png.result()
    gdb_ok = state['gdb_ok']
    if indicator_styles:
        written['indicators'] = {k: {'field': v['field'], 'scale': v['scale'], 'breaks': v['breaks']} for k, v in indicator_styles.items()}
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
