"""Calcolo anticipato di fasi indipendenti del modello, in un processo separato.

Appena `prepare` ha salvato OSM e Overture normalizzati (inizio del passo 2), un processo separato calcola, con le
funzioni originali del modello e dagli stessi file del run, i POI statici delle feature (passo 4), i programmi di
apertura delle attività (passo 5) e, quando i ricevitori sono pronti (passo 4), le matrici delle attività usate
dalla previsione. Quando il modello chiama quelle funzioni, il risultato anticipato viene restituito solo se gli
argomenti ricevuti coincidono esattamente (impronta di tutte le colonne e delle geometrie, dei profili, dei
programmi); altrimenti il modello calcola come sempre. SONAR_SPECULATIVE=0 disattiva.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

_JOB = {}


def _digest(*parts) -> str:
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, np.ndarray) and part.dtype.kind == 'O':      # testo: si usa il contenuto, non gli indirizzi
            h.update(pd.util.hash_pandas_object(pd.Series(part, dtype=object), index=False).to_numpy().tobytes())
        elif isinstance(part, np.ndarray):
            h.update(str(part.dtype).encode()); h.update(np.ascontiguousarray(part).tobytes())
        else:
            h.update(json.dumps(part, sort_keys=True, default=str).encode())
    return h.hexdigest()


def frame_parts(frame) -> list:
    """Contenuto completo di un (Geo)DataFrame per l'impronta: nomi e tipi delle colonne, valori, geometrie in WKB."""
    import shapely
    parts = [list(map(str, frame.columns)), [str(t) for t in frame.dtypes]]
    for name in frame.columns:
        column = frame[name]
        if str(column.dtype) == 'geometry':
            parts.append(np.asarray(shapely.to_wkb(column.to_numpy(), hex=True), dtype=object))
        else:
            try:
                parts.append(pd.util.hash_pandas_object(column, index=False).to_numpy())
            except TypeError:
                parts.append(column.astype(str).to_numpy(dtype=object))
    return parts


def static_key(places, osm, cfg) -> str:
    return _digest(*frame_parts(places), *frame_parts(osm), cfg)


def programs_key(places, osm, profiles, crs) -> str:
    import shapely
    return _digest(places.unit_id.astype(str).to_numpy(), shapely.get_coordinates(places.geometry.to_numpy()),
                   osm.unit_id.astype(str).to_numpy(), profiles, int(crs) if crs is not None else None, str(places.crs))


def matrices_key(points, places, programs) -> str:
    import shapely
    return _digest(shapely.get_coordinates(np.asarray(points.to_numpy() if hasattr(points, 'to_numpy') else points)),
                   places.program_id.to_numpy(), shapely.get_coordinates(places.geometry.to_numpy()), programs)


def _wait_flag(flag):
    parent = multiprocessing.parent_process()
    while not flag.exists():
        if parent is not None and not parent.is_alive():
            raise SystemExit(0)
        time.sleep(0.3)


def _save(path, data):
    pd.to_pickle(data, str(path) + '.part')
    os.replace(str(path) + '.part', path)


def _job(out_dir, code_paths, paths):
    import sys
    for folder in reversed(code_paths):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    import functools
    import geopandas as gpd
    from sonar import places as places_module
    from sonar import predict as predict_module
    from sonar.legacy import activity
    from sonar.prepare import FEATURE_CONFIG, HOURS_PLAN
    hours = activity()
    hours.profile_for = functools.lru_cache(maxsize=None)(hours.profile_for)
    out = Path(out_dir)
    paths = {k: Path(v) for k, v in paths.items()}
    started = time.monotonic()
    osm, places = gpd.read_parquet(out / 'osm_poi.parquet'), gpd.read_parquet(out / 'places.parquet')
    crs = places.crs.to_epsg()
    # POI statici delle feature (passo 4)
    cfg = json.loads(Path(FEATURE_CONFIG).read_text(encoding='utf-8'))
    key_static = static_key(places, osm, cfg)
    value = places_module.static_pois(places, osm, cfg)
    _save(paths['static'], {'key': key_static, 'value': value, 'seconds': round(time.monotonic() - started, 1)})
    # programmi di apertura (passo 5)
    profiles = json.loads(Path(HOURS_PLAN).read_text(encoding='utf-8'))['profiles']
    key_programs = programs_key(places, osm, profiles, crs)
    t0 = time.monotonic()
    dynamic, programs, report = places_module.activity_programs(places, osm, profiles, crs)
    _save(paths['programs'], {'key': key_programs, 'value': (dynamic, programs, report), 'seconds': round(time.monotonic() - t0, 1)})
    # matrici delle attività: servono i ricevitori (salvati alla fine del passo 3)
    _, models = predict_module.load_models()
    padded = places_module.pad_programs(programs, models)
    # le matrici si calcolano dai luoghi come la previsione li rilegge dal parquet salvato dal passo 5
    tmp = out / '_anticipo_luoghi.parquet'
    dynamic.to_parquet(tmp, index=False)
    places_saved = gpd.read_parquet(tmp)
    tmp.unlink()
    _wait_flag(paths['flag'])
    receivers = gpd.read_parquet(out / 'receivers.parquet')
    from sonar_app import parallel
    from sonar_app.fastfeatures import default_workers
    os.environ['SONAR_FEATURE_WORKERS'] = str(max(1, min(4, default_workers() - 2)))
    matrices_fn = parallel.parallel_program_matrices(predict_module.program_matrices, 'sonar.legacy', 'spatial_program_counts',
                                                     code_paths, lambda *_: None)
    matrices = matrices_fn(receivers.geometry, places_saved, padded)
    key_matrices = matrices_key(receivers.geometry, places_saved, padded)
    _save(paths['matrices'], {'key': key_matrices, 'value': matrices, 'seconds': round(time.monotonic() - started, 1)})


def prepare_dir():
    """Cartella del passo prepare del run in corso (SONAR_ROOT/data/processed/*_sonar_prepare_*)."""
    root = os.environ.get('SONAR_ROOT')
    if not root:
        return None
    found = sorted(Path(root).glob('data/processed/*_sonar_prepare_*'), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def start(out_dir, code_paths, receivers_ready=False) -> None:
    """Avvia il calcolo anticipato (una volta per run); `receivers_ready` sblocca le matrici delle attività."""
    if os.environ.get('SONAR_SPECULATIVE', '1') == '0' or out_dir is None:
        return
    out = Path(out_dir)
    if _JOB.get('process') is not None:
        if receivers_ready and _JOB['out'] == out:
            _JOB['paths']['flag'].touch()
        return
    if not all((out / f).exists() for f in ('osm_poi.parquet', 'places.parquet')):
        return
    paths = {'static': out / '_anticipo_statici.pkl', 'programs': out / '_anticipo_programmi.pkl',
             'matrices': out / '_anticipo_matrici.pkl', 'flag': out / '_anticipo_ricevitori_pronti'}
    for path in paths.values():
        if path.exists():
            path.unlink()
    if receivers_ready:
        paths['flag'].touch()
    process = multiprocessing.get_context('spawn').Process(target=_job, args=(str(out), list(code_paths), {k: str(v) for k, v in paths.items()}),
                                                           daemon=False)
    process.start()
    _JOB.update(process=process, paths=paths, out=out)


def start_before(original, code_paths):
    """La funzione del modello, preceduta dall'avvio del calcolo anticipato (passo 2 di prepare)."""
    def wrapped(*args, **kwargs):
        try:
            start(prepare_dir(), code_paths)
        except Exception:
            pass
        return original(*args, **kwargs)
    return wrapped


def _result(name):
    """Risultato anticipato `name`, aspettando il processo se sta ancora lavorando; None se non disponibile."""
    process = _JOB.get('process')
    if process is None:
        return None
    path = _JOB['paths'][name]
    if name == 'matrices' and not _JOB['paths']['flag'].exists():
        return None                          # ricevitori mai segnalati: il processo non calcolerà le matrici
    while not path.exists() and process.is_alive():
        time.sleep(0.2)
    if not path.exists():
        return None
    try:
        data = pd.read_pickle(path)
    except Exception:
        return None
    try:
        path.unlink()
    except OSError:
        pass
    if name == 'matrices':
        process.join(5)
    return data


def wrap_static(original, log=print):
    def static_pois(places, osm, feature_cfg):
        data = _result('static')
        if data is not None and data['key'] == static_key(places, osm, feature_cfg):
            log(f'  POI statici pronti (calcolati durante i passi 2-3, {data["seconds"]:.0f} s)')
            return data['value']
        return original(places, osm, feature_cfg)
    return static_pois


def wrap_programs(original, log=print):
    def activity_programs(places_in, osm_in, profiles, crs):
        data = _result('programs')
        if data is not None and data['key'] == programs_key(places_in, osm_in, profiles, crs):
            log(f'  programmi delle attività pronti (calcolati durante i passi 2-4, {data["seconds"]:.0f} s)')
            return data['value']
        return original(places_in, osm_in, profiles, crs)
    return activity_programs


def wrap_matrices(original, log=print):
    def program_matrices(points, places, programs, chunk=4000):
        data = _result('matrices')
        if data is not None and data['key'] == matrices_key(points, places, programs):
            log('  matrici delle attività pronte (calcolate durante il passo 4)')
            return data['value']
        return original(points, places, programs, chunk)
    return program_matrices
