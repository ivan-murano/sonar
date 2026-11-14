"""ESA WorldCover 2021 v200 (10 m): finestra dell'area letta dai GeoTIFF ottimizzati per il cloud."""
from __future__ import annotations

import math
import time
from pathlib import Path

from .. import net
from ..i18n import t
from . import Job, area_bounds

URL = 'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif'
LICENSE = {'publisher': 'ESA WorldCover consortium', 'license': 'CC BY 4.0', 'license_url': 'https://esa-worldcover.org/en/data-access',
           'attribution': '© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium'}


def tiles(bounds) -> list[str]:
    """Tile da 3x3 gradi (nome dell'angolo sud-ovest, es. N39E012) che intersecano il riquadro."""
    w, s, e, n = bounds
    names = []
    for lat in range(int(math.floor(s / 3) * 3), int(math.floor(n / 3) * 3) + 1, 3):
        for lon in range(int(math.floor(w / 3) * 3), int(math.floor(e / 3) * 3) + 1, 3):
            names.append(f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}")
    return names


def fetch(spec: dict, city, dest_dir: Path, job: Job) -> dict:
    import rasterio
    from rasterio.merge import merge
    bounds = area_bounds(city, float(spec.get('buffer_m', 1000)))
    margin = float(spec.get('margin_deg', 0.01))
    window = (bounds[0] - margin, bounds[1] - margin, bounds[2] + margin, bounds[3] + margin)
    job.report(0.0, t('dl_worldcover', job.language))
    sources, urls, method = [], [], 'COG window read'
    names = tiles(window)
    for i, tile in enumerate(names):
        if job.cancelled():
            raise net.Cancelled()
        url = URL.format(tile=tile)
        urls.append(url)
        try:
            source = rasterio.open(url)
        except Exception:
            local = net.download(url, job.cache / 'worldcover' / Path(url).name, cancelled=job.cancelled, max_bytes=800_000_000)
            source = rasterio.open(local)
            method = 'full tile download + local window'
        sources.append(source)
        job.report(0.3 * (i + 1) / len(names), t('dl_worldcover', job.language))
    data, transform = merge(sources, bounds=window, nodata=0)
    profile = sources[0].profile.copy()
    profile.update(driver='GTiff', height=data.shape[1], width=data.shape[2], transform=transform, count=1, compress='deflate', tiled=True, nodata=0)
    for key in ('interleave',):
        profile.pop(key, None)
    dest = dest_dir / f'{spec.get("_slug", "city")}_esa_worldcover_2021.tif'
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dest, 'w', **profile) as out:
        out.write(data[0], 1)
    for source in sources:
        source.close()
    job.report(1.0, t('dl_worldcover', job.language))
    return {'path': dest, 'source': {**LICENSE, 'dataset': 'ESA WorldCover 10 m 2021 v200', 'tiles': urls, 'method': method,
                                     'bounds_wgs84': list(window), 'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}}
