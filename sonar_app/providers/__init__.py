"""Fornitori di dati: scaricano ciò che il modello dichiara in "inputs" del manifest.

Ogni fornitore espone fetch(spec, city, dest_dir, job) -> {'path': Path, 'source': {...}}.
`source` descrive editore, URL, versione, licenza e attribuzione e finisce in fonti_dati.json.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Job:
    """Servizi del lavoro in corso offerti ai fornitori."""
    language: str
    cache: Path
    report: Callable[[float, str], None]     # avanzamento nel tratto del fornitore (0..1) e messaggio
    log: Callable[[str], None]
    cancelled: Callable[[], bool]


def area_bounds(city, buffer_m: float = 0.0):
    """Riquadro WGS84 del confine allargato di buffer_m metri (calcolato in ETRS89-LAEA)."""
    import geopandas as gpd
    from shapely.geometry import shape
    series = gpd.GeoSeries([shape(city.geometry)], crs=4326)
    if buffer_m:
        series = series.to_crs(3035).buffer(buffer_m).to_crs(4326)
    return tuple(float(v) for v in series.total_bounds)


def area_polygon(city, buffer_m: float = 0.0):
    import geopandas as gpd
    from shapely.geometry import shape
    series = gpd.GeoSeries([shape(city.geometry)], crs=4326)
    if buffer_m:
        series = series.to_crs(3035).buffer(buffer_m).to_crs(4326)
    return series.iloc[0]


def registry() -> dict:
    """Fornitori per nome. Con SONAR_LOCAL_INPUTS = file JSON {provider: percorso} i file locali
    sostituiscono i download (prove senza rete, sviluppo del modello)."""
    import json
    import os
    from . import osm, overture, population, worldcover
    fetchers = {'osm_pbf': osm.fetch, 'overture_places': overture.fetch, 'esa_worldcover': worldcover.fetch,
                'ghsl_population': population.fetch}
    if os.environ.get('SONAR_LOCAL_INPUTS'):
        mapping = json.loads(Path(os.environ['SONAR_LOCAL_INPUTS']).read_text(encoding='utf-8'))
        for provider, path in mapping.items():
            fetchers[provider] = _local_fetcher(provider, Path(path))
    return fetchers


def _local_fetcher(provider: str, source: Path):
    def fetch(spec, city, dest_dir, job):
        import shutil
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f'{spec.get("_slug", "city")}_{source.name}'
        job.report(0.0, f'{provider}: {source.name}')
        shutil.copy2(source, dest)
        job.report(1.0, f'{provider}: {source.name}')
        return {'path': dest, 'source': {'dataset': provider, 'local_file': str(source), 'note': 'SONAR_LOCAL_INPUTS'}}
    return fetch


# Nome della sottocartella in "Dati di input" per ciascun fornitore (uguale nelle due lingue).
FOLDER_NAMES = {'osm_pbf': 'OpenStreetMap', 'overture_places': 'Overture Places', 'esa_worldcover': 'ESA WorldCover', 'ghsl_population': 'GHSL'}
