"""Overture Maps Places nel riquadro dell'area (ultima release del catalogo STAC), GeoParquet nativo."""
from __future__ import annotations

import time
from pathlib import Path

from .. import net
from ..i18n import t
from . import Job, area_bounds

LICENSE = {'publisher': 'Overture Maps Foundation and data providers', 'license': 'CDLA Permissive 2.0 (most providers); see attribution page',
           'license_url': 'https://docs.overturemaps.org/attribution/', 'attribution': '© Overture Maps Foundation'}


def fetch(spec: dict, city, dest_dir: Path, job: Job) -> dict:
    import pyarrow.parquet as pq
    from overturemaps import core
    bounds = area_bounds(city, float(spec.get('buffer_m', 1000)))
    kind = spec.get('type', 'place')
    release = spec.get('release') or core.get_latest_release()
    max_rows = int(spec.get('max_rows', 3_000_000))
    job.report(0.0, t('dl_places', job.language, rows=0))
    reader = core.record_batch_reader(kind, bbox=tuple(bounds), release=release, stac=True, connect_timeout=30, request_timeout=120)
    if reader is None:
        raise RuntimeError('Overture: nessun dato nel riquadro')
    dest = dest_dir / f'{spec.get("_slug", "city")}_overture_{kind}.parquet'
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    rows, writer = 0, None
    try:
        for batch in reader:
            if job.cancelled():
                raise net.Cancelled()
            if batch.num_rows == 0:
                continue
            if writer is None:
                writer = pq.ParquetWriter(part, batch.schema, compression='zstd')
            writer.write_batch(batch)
            rows += batch.num_rows
            job.report(min(0.95, rows / 200_000), t('dl_places', job.language, rows=f'{rows:,}'))
            if rows > max_rows:
                raise ValueError(f'Overture: oltre {max_rows:,} righe, area troppo grande')
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        raise RuntimeError('Overture: risposta vuota')
    part.replace(dest)
    job.report(1.0, t('dl_places', job.language, rows=f'{rows:,}'))
    return {'path': dest, 'source': {**LICENSE, 'dataset': f'Overture Maps {kind}', 'release': release, 'rows': rows, 'bbox_wgs84': list(bounds),
                                     'url': f's3://overturemaps-us-west-2/release/{release}/theme={core.type_theme_map[kind]}/type={kind}/',
                                     'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}}
