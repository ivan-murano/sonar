"""Esecuzione su più processi delle fasi del modello che lavorano a blocchi indipendenti.

Ogni funzione qui sotto riceve la funzione originale del modello e la applica, identica, a blocchi di
ricevitori distribuiti su più processi; poi riunisce i blocchi nello stesso ordine. Le righe sono indipendenti
(lo dice il modello stesso, che già lavora a blocchi in sequenza), quindi il risultato è identico alla
chiamata originale. Se il modello cambia queste funzioni, i processi chiamano la versione nuova; se cambia
la loro firma, l'adattatore usa le originali (vedi `wrap`).

I processi figli importano il codice del modello dalle cartelle indicate in `code_paths`.
"""
from __future__ import annotations

import inspect
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from .fastfeatures import default_workers

_STATE: dict = {}


def _init(code_paths, context_path, threads):
    import sys
    for folder in reversed(code_paths):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    os.environ['OMP_NUM_THREADS'] = str(threads)
    try:
        from threadpoolctl import threadpool_limits
        _STATE['limits'] = threadpool_limits(threads)
    except Exception:
        pass
    _STATE['context'] = pd.read_pickle(context_path) if context_path else None


def _pool(workers, code_paths, context_path=None, threads=1):
    return ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                               initializer=_init, initargs=(list(code_paths), str(context_path) if context_path else None, threads))


def _resolve(module_name, attribute):
    import importlib
    return getattr(importlib.import_module(module_name), attribute)


def signature_matches(function, expected: list[str]) -> bool:
    """La firma della funzione del modello è ancora quella per cui è scritto il parallelizzatore?"""
    try:
        names = list(inspect.signature(function).parameters)
    except (TypeError, ValueError):
        return False
    return names[:len(expected)] == expected


# ---------------------------------------------------------------- ricevitori (prepare, passo 3)

def _receivers_job(module_name, attribute, kind, start, chunk, upath, rpath):
    select = _resolve(module_name, attribute)          # nei processi figli è la funzione originale del modello
    units, buildings, boundary, worldcover, crs = _STATE['context']
    frame = units[kind]
    u, r = select({kind: frame.iloc[start:start + chunk]}, buildings, boundary, worldcover, crs, lambda *_: None)
    upath, rpath = Path(upath), Path(rpath)
    u.to_parquet(upath.with_suffix('.part'), index=False); r.to_parquet(rpath.with_suffix('.part'), index=False)
    rpath.with_suffix('.part').replace(rpath); upath.with_suffix('.part').replace(upath)
    return kind, start, len(frame)


def parallel_receivers(original, module_name, attribute, code_paths):
    """`select_receivers(units, buildings, boundary_metric, worldcover_path, crs, log, parts_dir, chunk)`.

    I blocchi mancanti in `parts_dir` sono calcolati in parallelo con la funzione originale, scrivendo gli
    stessi file del calcolo sequenziale; poi la funzione originale riunisce e verifica i blocchi."""
    def select_receivers(units, buildings, boundary_metric, worldcover_path, crs, log=print, parts_dir=None, chunk=5000):
        if parts_dir is not None:
            parts_dir = Path(parts_dir); parts_dir.mkdir(exist_ok=True)
            jobs = []
            for kind in ('h3', 'road'):
                if kind not in units:
                    continue
                for start in range(0, len(units[kind]), chunk):
                    upath, rpath = parts_dir / f'{kind}_{start:07d}_units.parquet', parts_dir / f'{kind}_{start:07d}_receivers.parquet'
                    if not (upath.exists() and rpath.exists()):
                        jobs.append((kind, start, upath, rpath))
            workers = min(default_workers(), len(jobs))
            if workers > 1:
                context = parts_dir / '_contesto.pkl'
                pd.to_pickle((units, buildings, boundary_metric, str(worldcover_path), crs), context)
                started = time.monotonic()
                try:
                    with _pool(workers, code_paths, context) as pool:
                        futures = [pool.submit(_receivers_job, module_name, attribute, k, s, chunk, str(u), str(r)) for k, s, u, r in jobs]
                        for future in as_completed(futures):
                            kind, start, total = future.result()
                            log(f'  {kind}: {min(start + chunk, total):,}/{total:,} unità')
                    log(f'  ricevitori calcolati su {workers} processi in {time.monotonic() - started:.0f} s')
                except Exception as exc:
                    log(f'  processi paralleli non disponibili per i ricevitori ({type(exc).__name__}: {exc}); calcolo sequenziale')
                finally:
                    try:
                        context.unlink()
                    except OSError:
                        pass
        return original(units, buildings, boundary_metric, worldcover_path, crs, log, parts_dir=parts_dir, chunk=chunk)
    return select_receivers


# ---------------------------------------------------------------- matrici delle attività (predict)

def _program_job(start, stop, chunk):
    from scipy.sparse import vstack
    function, points, places, programs = _STATE['function'], _STATE['context'][0], _STATE['context'][1], _STATE['context'][2]
    parts = [function(points.iloc[s:min(s + chunk, stop)], places, programs) for s in range(start, stop, chunk)]
    return start, {radius: vstack([p[radius] for p in parts]).tocsr() for radius in parts[0]}


def _program_init(code_paths, context_path, threads, module_name, factory):
    _init(code_paths, context_path, threads)
    _STATE['function'] = _resolve(module_name, factory)()


def parallel_program_matrices(original, function_module, function_factory, code_paths, log=print):
    """`program_matrices(points, places, programs, chunk)`: stessi blocchi da `chunk` ricevitori, in parallelo."""
    def program_matrices(points, places, programs, chunk=4000):
        from scipy.sparse import vstack
        n = len(points)
        workers = min(default_workers(), max(1, n // (chunk * 2)))
        if workers <= 1:
            return original(points, places, programs, chunk)
        span = chunk * max(1, -(-n // (chunk * workers * 4)))      # ~4 lavori per processo, multipli di chunk
        context = Path(os.environ.get('SONAR_ROOT', '.')) / f'_programmi_{os.getpid()}.pkl'
        pd.to_pickle((points, places, programs), context)
        started = time.monotonic()
        try:
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'), initializer=_program_init,
                                     initargs=(list(code_paths), str(context), 1, function_module, function_factory)) as pool:
                parts = dict(f.result() for f in as_completed([pool.submit(_program_job, s, min(s + span, n), chunk) for s in range(0, n, span)]))
            log(f'  matrici delle attività calcolate su {workers} processi in {time.monotonic() - started:.0f} s')
        except Exception as exc:
            log(f'  processi paralleli non disponibili per le matrici ({type(exc).__name__}: {exc}); calcolo sequenziale')
            return original(points, places, programs, chunk)
        finally:
            try:
                context.unlink()
            except OSError:
                pass
        ordered = [parts[s] for s in sorted(parts)]
        return {radius: vstack([p[radius] for p in ordered]).tocsr() for radius in ordered[0]}
    return program_matrices


# ---------------------------------------------------------------- previsione (predict)

def _predict_job(module_name, attribute, start, spatial, matrices, kwargs):
    function = _resolve(module_name, attribute)        # nei processi figli è la funzione originale del modello
    programs, models, calendar, scenarios = _STATE['context']
    return start, function(spatial, matrices, programs, models, calendar, scenarios, **kwargs)


def parallel_predict(original, module_name, attribute, code_paths, threads_per_worker=2):
    """`predict_scenarios(spatial, matrices, programs, models, calendar, scenarios, chunk_size, progress)`.

    I ricevitori sono divisi in parti contigue (multipli di chunk_size), ognuna prevista dalla funzione
    originale in un processo; le tabelle risultanti sono riunite nell'ordine dei ricevitori."""
    def predict_scenarios(spatial, matrices, programs, models, calendar, scenarios, chunk_size=2000, progress=None):
        n = len(spatial)
        workers = min(max(1, default_workers() * 2 // threads_per_worker), max(1, n // (chunk_size * 4)))
        if workers <= 1:
            return original(spatial, matrices, programs, models, calendar, scenarios, chunk_size=chunk_size, progress=progress)
        span = chunk_size * max(1, -(-n // (chunk_size * workers * 3)))
        context = Path(os.environ.get('SONAR_ROOT', '.')) / f'_previsione_{os.getpid()}.pkl'
        pd.to_pickle((programs, models, calendar, scenarios), context)
        kinds = list(scenarios)
        try:
            with _pool(workers, code_paths, context, threads_per_worker) as pool:
                futures = [pool.submit(_predict_job, module_name, attribute, s, spatial.iloc[s:s + span].reset_index(drop=True),
                                       {r: m[s:s + span] for r, m in matrices.items()}, {'chunk_size': chunk_size})
                           for s in range(0, n, span)]
                parts, done = {}, 0
                for future in as_completed(futures):
                    start, result = future.result()
                    parts[start] = result
                    done += len(next(iter(result.values())))
                    if progress:
                        for kind in kinds:
                            progress(kind, done, n)
        except Exception:
            return original(spatial, matrices, programs, models, calendar, scenarios, chunk_size=chunk_size, progress=progress)
        finally:
            try:
                context.unlink()
            except OSError:
                pass
        results = {}
        for kind in kinds:
            frame = pd.concat([parts[s][kind] for s in sorted(parts)], ignore_index=True)
            if not frame.unit_id.equals(spatial.unit_id.reset_index(drop=True)):
                raise AssertionError('Ordine dei ricevitori non conservato nella previsione parallela')
            results[kind] = frame
        return results
    return predict_scenarios


# ---------------------------------------------------------------- segmenti stradali (prepare, passo 2)

def _segments_job(module_name, attribute, ways, boundary, crs, max_length):
    function = _resolve(module_name, attribute)
    return function(ways, boundary, crs, max_length)


def parallel_road_segments(original, module_name, attribute, code_paths, log=print):
    """`road_segments(ways, boundary_metric, crs, max_length)`: way divise in gruppi, ognuno con la funzione originale.

    La funzione spezza le way ai nodi condivisi contati su tutte le way in ingresso (comprese quelle escluse come
    tunnel). Per conservare quel conteggio, ogni gruppo riceve in più una way fittizia con `tunnel=yes`, che contiene
    i nodi condivisi a livello globale: non produce segmenti e rende «condivisi» gli stessi nodi del calcolo unico.
    I gruppi sono riuniti nell'ordine originale e i duplicati tolti come fa la funzione (si tiene il primo)."""
    def road_segments(ways, boundary_metric, crs, max_length=50):
        from collections import Counter
        import geopandas as gpd
        workers = min(default_workers(), max(1, len(ways) // 20000))
        if workers <= 1:
            return original(ways, boundary_metric, crs, max_length)
        counts = Counter(node for w in ways for node in set(w['nodes']))
        shared = [node for node, c in counts.items() if c > 1]
        ghost = {'id': -1, 'version': None, 'nodes': shared, 'coords': [(0.0, 0.0)] * len(shared), 'tags': {'tunnel': 'yes', 'highway': 'ghost'}}
        size = -(-len(ways) // (workers * 3))
        groups = [ways[i:i + size] + [ghost] for i in range(0, len(ways), size)]
        started = time.monotonic()
        try:
            with _pool(workers, code_paths) as pool:
                results = list(pool.map(_segments_job, *zip(*[(module_name, attribute, g, boundary_metric, crs, max_length) for g in groups])))
        except Exception as exc:
            log(f'  processi paralleli non disponibili per i segmenti ({type(exc).__name__}: {exc}); calcolo sequenziale')
            return original(ways, boundary_metric, crs, max_length)
        frames = [r[0] for r in results if len(r[0])]
        roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs) if frames else results[0][0]
        duplicated = int(roads.unit_id.duplicated().sum())
        if duplicated:
            roads = roads.drop_duplicates('unit_id').reset_index(drop=True)
        info = dict(results[0][1])
        info['roads_segments'] = len(roads)
        info['roads_length_m_total'] = float(roads.length.sum())
        info['tunnel_ways_excluded'] = sum(r[1]['tunnel_ways_excluded'] for r in results) - len(groups)
        info['duplicate_segment_ids_dropped'] = sum(r[1]['duplicate_segment_ids_dropped'] for r in results) + duplicated
        log(f'  segmenti stradali calcolati su {workers} processi in {time.monotonic() - started:.0f} s')
        return roads, info
    return road_segments
