"""Calcolo anticipato di fasi indipendenti del modello, mentre le feature statiche occupano gli altri core.

Durante il passo 4 di `prepare` (feature statiche) un processo separato calcola, con le funzioni originali del
modello e dagli stessi file del run, i programmi di apertura delle attività (passo 5) e le matrici delle attività
usate dalla previsione. Quando il modello chiama quelle funzioni, il risultato anticipato viene restituito solo se
gli argomenti ricevuti coincidono esattamente (impronta degli identificativi, delle coordinate, dei profili e dei
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


def programs_key(places, osm, profiles, crs) -> str:
    import shapely
    return _digest(places.unit_id.astype(str).to_numpy(), shapely.get_coordinates(places.geometry.to_numpy()),
                   osm.unit_id.astype(str).to_numpy(), profiles, int(crs) if crs is not None else None, str(places.crs))


def matrices_key(points, places, programs) -> str:
    import shapely
    return _digest(shapely.get_coordinates(np.asarray(points.to_numpy() if hasattr(points, 'to_numpy') else points)),
                   places.program_id.to_numpy(), shapely.get_coordinates(places.geometry.to_numpy()), programs)


def _job(out_dir, code_paths, programs_path, matrices_path, crs):
    import sys
    for folder in reversed(code_paths):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    import functools
    import geopandas as gpd
    from sonar import places as places_module
    from sonar import predict as predict_module
    from sonar.legacy import activity
    from sonar.prepare import HOURS_PLAN
    hours = activity()
    hours.profile_for = functools.lru_cache(maxsize=None)(hours.profile_for)
    out = Path(out_dir)
    started = time.monotonic()
    osm, places = gpd.read_parquet(out / 'osm_poi.parquet'), gpd.read_parquet(out / 'places.parquet')
    profiles = json.loads(Path(HOURS_PLAN).read_text(encoding='utf-8'))['profiles']
    key_programs = programs_key(places, osm, profiles, crs)
    dynamic, programs, report = places_module.activity_programs(places, osm, profiles, crs)
    t_programs = time.monotonic() - started
    pd.to_pickle({'key': key_programs, 'value': (dynamic, programs, report), 'seconds': round(t_programs, 1)}, programs_path + '.part')
    os.replace(programs_path + '.part', programs_path)
    receivers = gpd.read_parquet(out / 'receivers.parquet')
    _, models = predict_module.load_models()
    padded = places_module.pad_programs(programs, models)
    # le matrici si calcolano dai luoghi come la previsione li rilegge dal parquet salvato dal passo 5
    tmp = out / '_anticipo_luoghi.parquet'
    dynamic.to_parquet(tmp, index=False)
    places_saved = gpd.read_parquet(tmp)
    tmp.unlink()
    from sonar_app import parallel
    from sonar_app.fastfeatures import default_workers
    os.environ['SONAR_FEATURE_WORKERS'] = str(max(1, min(3, default_workers() // 2)))
    matrices_fn = parallel.parallel_program_matrices(predict_module.program_matrices, 'sonar.legacy', 'spatial_program_counts',
                                                     code_paths, lambda *_: None)
    matrices = matrices_fn(receivers.geometry, places_saved, padded)
    key_matrices = matrices_key(receivers.geometry, places_saved, padded)
    pd.to_pickle({'key': key_matrices, 'value': matrices, 'seconds': round(time.monotonic() - started, 1)}, matrices_path + '.part')
    os.replace(matrices_path + '.part', matrices_path)


def start(out_dir, code_paths, crs) -> None:
    """Avvia il calcolo anticipato (una volta per run)."""
    if os.environ.get('SONAR_SPECULATIVE', '1') == '0' or _JOB.get('process') is not None:
        return
    out = Path(out_dir)
    if not all((out / f).exists() for f in ('osm_poi.parquet', 'places.parquet', 'receivers.parquet')):
        return
    paths = {'programs': out / '_anticipo_programmi.pkl', 'matrices': out / '_anticipo_matrici.pkl'}
    for path in paths.values():
        if path.exists():
            path.unlink()
    process = multiprocessing.get_context('spawn').Process(
        target=_job, args=(str(out), list(code_paths), str(paths['programs']), str(paths['matrices']), crs), daemon=False)
    process.start()
    _JOB.update(process=process, paths=paths)


def _result(name):
    """Risultato anticipato `name`, aspettando il processo se sta ancora lavorando; None se non disponibile."""
    process = _JOB.get('process')
    if process is None:
        return None
    path = _JOB['paths'][name]
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


def wrap_programs(original, log=print):
    def activity_programs(places_in, osm_in, profiles, crs):
        data = _result('programs')
        if data is not None and data['key'] == programs_key(places_in, osm_in, profiles, crs):
            log(f'  programmi delle attività già calcolati in parallelo alle feature ({data["seconds"]:.0f} s)')
            return data['value']
        return original(places_in, osm_in, profiles, crs)
    return activity_programs


def wrap_matrices(original, log=print):
    def program_matrices(points, places, programs, chunk=4000):
        data = _result('matrices')
        if data is not None and data['key'] == matrices_key(points, places, programs):
            log('  matrici delle attività già calcolate in parallelo alle feature')
            return data['value']
        return original(points, places, programs, chunk)
    return program_matrices
