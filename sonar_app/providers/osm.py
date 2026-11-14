"""OpenStreetMap: estratto regionale Geofabrik più piccolo che copre l'area, ritagliato sulla città.

L'estratto regionale resta in cache (riusato per le città vicine) ed è verificato con il file
.md5 pubblicato da Geofabrik. Nella consegna va solo il ritaglio: oggetti con tag che cadono nel
riquadro, vie complete (anche i nodi fuori riquadro) e multipoligoni che le usano.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import net
from ..i18n import t
from . import Job, area_bounds, area_polygon

INDEX_URL = 'https://download.geofabrik.de/index-v1.json'
INDEX_MAX_AGE_S = 7 * 24 * 3600
EXTRACT_MAX_AGE_S = 14 * 24 * 3600
LICENSE = {'publisher': 'OpenStreetMap contributors; extract by Geofabrik GmbH', 'license': 'ODbL 1.0',
           'license_url': 'https://www.openstreetmap.org/copyright', 'attribution': '© OpenStreetMap contributors'}


def geofabrik_index(cache: Path) -> dict:
    path = cache / 'geofabrik' / 'index-v1.json'
    if path.exists() and time.time() - path.stat().st_mtime < INDEX_MAX_AGE_S:
        return json.loads(path.read_text(encoding='utf-8'))
    net.download(INDEX_URL, path.with_suffix('.tmp.json'))
    path.with_suffix('.tmp.json').replace(path)
    return json.loads(path.read_text(encoding='utf-8'))


def select_extract(index: dict, polygon) -> dict:
    """Estratto di area minima la cui geometria copre interamente il poligono."""
    from shapely.geometry import shape
    best = None
    for feature in index['features']:
        props = feature.get('properties', {})
        if not feature.get('geometry') or 'pbf' not in props.get('urls', {}):
            continue
        geometry = shape(feature['geometry'])
        if geometry.covers(polygon) and (best is None or geometry.area < best[0]):
            best = (geometry.area, props)
    if best is None:
        raise LookupError('Nessun estratto Geofabrik copre l’area della città')
    return best[1]


def clip_pbf(source: Path, dest: Path, bounds, cancelled=lambda: False, report=lambda f: None) -> dict:
    """Ritaglio con pyosmium; restituisce i conteggi degli oggetti scritti."""
    import osmium
    w, s, e, n = bounds
    size = source.stat().st_size
    index = 'sparse_mem_array' if size < 1_500_000_000 else f'sparse_file_array,{dest.with_suffix(".idx")}'
    nodes, ways, relations = set(), set(), 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part.pbf')
    if tmp.exists():
        tmp.unlink()

    def inside(location) -> bool:
        return location.valid() and w <= location.lon <= e and s <= location.lat <= n

    with osmium.BackReferenceWriter(str(tmp), ref_src=str(source), overwrite=True) as writer:
        processor = osmium.FileProcessor(str(source)).with_locations(index).with_filter(osmium.filter.EmptyTagFilter())
        for count, obj in enumerate(processor):
            if count % 200_000 == 0:
                if cancelled():
                    raise net.Cancelled()
                report(min(0.95, count / max(1.0, size / 60)))
            if obj.is_node():
                if inside(obj.location):
                    writer.add_node(obj); nodes.add(obj.id)
            elif obj.is_way():
                if any(inside(node.location) for node in obj.nodes):
                    writer.add_way(obj); ways.add(obj.id)
            elif obj.is_relation():
                if obj.tags.get('type') == 'multipolygon' and any(
                        (m.type == 'w' and m.ref in ways) or (m.type == 'n' and m.ref in nodes) for m in obj.members):
                    writer.add_relation(obj); relations += 1
    tmp.replace(dest)
    return {'tagged_nodes': len(nodes), 'ways': len(ways), 'multipolygons': relations}


def fetch(spec: dict, city, dest_dir: Path, job: Job) -> dict:
    buffer_m = float(spec.get('buffer_m', 1000))
    margin_m = float(spec.get('clip_margin_m', 1000))
    polygon = area_polygon(city, buffer_m + margin_m)
    job.report(0.0, t('dl_osm_index', job.language))
    extract = select_extract(geofabrik_index(job.cache), polygon)
    url = extract['urls']['pbf']
    cached = job.cache / 'geofabrik' / url.rsplit('/', 1)[-1]
    md5 = net.get_text(url + '.md5').split()[0]
    fresh = cached.exists() and time.time() - cached.stat().st_mtime < EXTRACT_MAX_AGE_S
    if fresh and net.file_md5(cached) == md5:
        job.report(0.6, t('dl_osm_cached', job.language, name=extract.get('name', extract['id'])))
    else:
        def progress(done, total):
            job.report(0.6 * done / total if total else 0.3,
                       t('dl_osm', job.language, name=extract.get('name', extract['id']), done=net.human_bytes(done), total=net.human_bytes(total)))
        net.download(url, cached, progress=progress, cancelled=job.cancelled, expected_md5=md5)
    job.report(0.6, t('dl_osm_clip', job.language))
    bounds = area_bounds(city, buffer_m + margin_m)
    slug = spec.get('_slug', 'city')
    dest = dest_dir / f'{slug}_openstreetmap.osm.pbf'
    counts = clip_pbf(cached, dest, bounds, job.cancelled, lambda f: job.report(0.6 + 0.4 * f, t('dl_osm_clip', job.language)))
    job.report(1.0, t('dl_osm_clip', job.language))
    return {'path': dest, 'source': {**LICENSE, 'dataset': 'OpenStreetMap', 'extract_id': extract['id'], 'extract_name': extract.get('name'),
                                     'url': url, 'md5_regional_extract': md5, 'clip_bounds_wgs84': list(bounds), 'objects': counts,
                                     'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(cached.stat().st_mtime))}}
