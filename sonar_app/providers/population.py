"""Popolazione residente GHS-POP R2023A (JRC, griglia 100 m, epoca 2020) ritagliata sull'area della città.

Le tile 1000 x 1000 km (Mollweide, ESRI:54009) si scaricano una volta nella cache e servono a tutte le città
vicine; nella consegna va solo la finestra della città in GeoTIFF.
Citazione: Schiavina M., Freire S., Carioli A., MacManus K. (2023) GHS-POP R2023A, European Commission JRC,
doi:10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE.
"""
from __future__ import annotations

import math
import time
import zipfile
from pathlib import Path

from .. import net
from ..i18n import t
from . import Job, area_polygon

EPOCH = 2020
BASE = ('https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/'
        'GHS_POP_E{epoch}_GLOBE_R2023A_54009_100/V1-0/tiles/')
TILE = 'GHS_POP_E{epoch}_GLOBE_R2023A_54009_100_V1_0_R{row}_C{col}.zip'
ORIGIN = (-18041000.0, 9000000.0)
TILE_M = 1_000_000.0
MOLLWEIDE = 'ESRI:54009'
LICENSE = {'publisher': 'European Commission, Joint Research Centre (GHSL)',
           'license': 'riuso autorizzato con citazione della fonte (Commission Decision 2011/833/EU)',
           'license_url': 'https://ghsl.jrc.ec.europa.eu/download.php',
           'attribution': 'Schiavina M., Freire S., Carioli A., MacManus K. (2023) GHS-POP R2023A - GHS population grid '
                          'multitemporal (1975-2030). European Commission, JRC. doi:10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE'}


def tiles(bounds_moll) -> list[tuple[int, int]]:
    xmin, ymin, xmax, ymax = bounds_moll
    x0, y0 = ORIGIN
    cols = range(int(math.floor((xmin - x0) / TILE_M)) + 1, int(math.floor((xmax - x0) / TILE_M)) + 2)
    rows = range(int(math.floor((y0 - ymax) / TILE_M)) + 1, int(math.floor((y0 - ymin) / TILE_M)) + 2)
    return [(r, c) for r in rows for c in cols]


def fetch(spec: dict, city, dest_dir: Path, job: Job) -> dict:
    import geopandas as gpd
    import rasterio
    from rasterio.merge import merge
    poly = gpd.GeoSeries([area_polygon(city, float(spec.get('buffer_m', 200)))], crs=4326).to_crs(MOLLWEIDE)
    xmin, ymin, xmax, ymax = poly.total_bounds
    window = (xmin - 200, ymin - 200, xmax + 200, ymax + 200)
    names = tiles(window)
    job.report(0.0, t('dl_population', job.language))
    sources, urls = [], []
    for i, (row, col) in enumerate(names):
        if job.cancelled():
            raise net.Cancelled()
        name = TILE.format(epoch=EPOCH, row=row, col=col)
        url = BASE.format(epoch=EPOCH) + name
        urls.append(url)
        cached = job.cache / 'ghsl' / name
        if not cached.exists():
            def progress(done, total, i=i):
                job.report(0.9 * (i + (done / total if total else 0.5)) / len(names),
                           t('dl_population_bytes', job.language, done=net.human_bytes(done), total=net.human_bytes(total)))
            net.download(url, cached, progress=progress, cancelled=job.cancelled)
        with zipfile.ZipFile(cached) as archive:
            member = next(n for n in archive.namelist() if n.lower().endswith('.tif'))
        sources.append(f'/vsizip/{cached.as_posix()}/{member}')
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f'{spec.get("_slug", "city")}_popolazione_GHSL_{EPOCH}.tif'
    opened = [rasterio.open(s) for s in sources]
    try:
        data, transform = merge(opened, bounds=window)
        profile = opened[0].profile
    finally:
        for src in opened:
            src.close()
    profile.update(driver='GTiff', height=data.shape[1], width=data.shape[2], transform=transform, compress='deflate', tiled=True,
                   blockxsize=256, blockysize=256)
    with rasterio.open(dest, 'w', **profile) as out:
        out.write(data)
    job.report(1.0, t('dl_population', job.language))
    return {'path': dest, 'source': {**LICENSE, 'dataset': f'GHS-POP R2023A, epoca {EPOCH}, 100 m', 'urls': urls, 'tiles': [f'R{r}_C{c}' for r, c in names],
                                     'crs': MOLLWEIDE, 'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}}
