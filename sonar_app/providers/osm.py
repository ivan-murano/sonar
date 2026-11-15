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


def clip_pbf_simple(source: Path, dest: Path, bounds, cancelled=lambda: False, report=lambda f: None) -> dict:
    """Ritaglio oggetto per oggetto (metodo originale, più lento); restituisce i conteggi degli oggetti scritti."""
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


def clip_pbf(source: Path, dest: Path, bounds, cancelled=lambda: False, report=lambda f: None) -> dict:
    """Ritaglio con pyosmium; restituisce i conteggi degli oggetti scritti.

    Regola: nodi con tag dentro il riquadro, way con almeno un vertice dentro, multipoligoni con un membro
    scelto, più i riferimenti all'indietro (BackReferenceWriter). Prima lettura: le coordinate delle way arrivano
    dal C++ in WKB e il test dei vertici è vettoriale; riferimenti completati in C++ e seconda lettura filtrata per
    id. File identico al ritaglio oggetto per oggetto (`clip_pbf_simple`), che resta come riserva."""
    try:
        return _clip_pbf_fast(source, dest, bounds, cancelled, report)
    except net.Cancelled:
        raise
    except Exception:
        return clip_pbf_simple(source, dest, bounds, cancelled, report)


def _clip_pbf_fast(source: Path, dest: Path, bounds, cancelled, report) -> dict:
    import numpy as np
    import osmium
    w, s, e, n = bounds
    size = source.stat().st_size
    index = 'sparse_mem_array' if size < 1_500_000_000 else f'sparse_file_array,{dest.with_suffix(".idx")}'
    wkb = osmium.geom.WKBFactory()
    nodes, ways, relations = set(), set(), set()
    batch_ids, batch_wkb, slow = [], [], []

    def flush():
        if not batch_ids:
            return
        # WKB LineString (esadecimale): 1 byte ordine, 4 tipo, 4 numero di punti, poi coppie di double
        sizes = np.fromiter(map(len, batch_wkb), dtype=np.int64, count=len(batch_wkb)) // 2
        raw = np.frombuffer(bytes.fromhex(''.join(batch_wkb)), dtype=np.uint8)
        starts = np.cumsum(sizes) - sizes
        little = raw[starts] == 1
        npts = (sizes - 9) // 16
        owner = np.repeat(np.arange(len(sizes)), npts)
        k = np.arange(owner.size) - np.repeat(np.cumsum(npts) - npts, npts)
        base = starts[owner] + 9 + 16 * k
        def doubles(offsets):
            b = raw[offsets[:, None] + np.arange(8)]
            v = b.copy().view('<f8').ravel()
            big = ~little[owner]
            if big.any():
                v[big] = b[big][:, ::-1].copy().view('<f8').ravel()
            return v
        lon, lat = doubles(base), doubles(base + 8)
        inside = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        hit = np.zeros(len(batch_ids), bool); hit[owner[inside]] = True
        ids = np.asarray(batch_ids, dtype=np.int64)
        ways.update(ids[hit].tolist())
        batch_ids.clear(); batch_wkb.clear()

    def inside(location) -> bool:
        return location.valid() and w <= location.lon <= e and s <= location.lat <= n

    class FirstPass(osmium.SimpleHandler):
        """Callback dal C++ (più leggeri degli oggetti di FileProcessor); stessa regola, stesso ordine."""
        count = 0

        def tick(self):
            self.count += 1
            if self.count % 200_000 == 0:
                if cancelled():
                    raise net.Cancelled()
                report(min(0.6, self.count / max(1.0, size / 60) * 0.6))

        def node(self, obj):
            self.tick()
            if inside(obj.location):
                nodes.add(obj.id)

        def way(self, obj):
            self.tick()
            try:
                batch_wkb.append(wkb.create_linestring(obj, use_nodes=osmium.geom.use_nodes.ALL))
                batch_ids.append(obj.id)
            except Exception:            # posizioni mancanti o way degeneri: controllo nodo per nodo
                if any(inside(node.location) for node in obj.nodes):
                    ways.add(obj.id)
            if len(batch_ids) >= 200_000:
                flush()

        def relation(self, obj):
            self.tick()
            flush()
            if obj.tags.get('type') == 'multipolygon' and any(
                    (m.type == 'w' and m.ref in ways) or (m.type == 'n' and m.ref in nodes) for m in obj.members):
                relations.add(obj.id)
                tracker.add_references(obj)          # membri, come BackReferenceWriter.add_relation

    tracker = osmium.IdTracker()
    locations = osmium.NodeLocationsForWays(osmium.index.create_map(index))
    locations.ignore_errors()
    with osmium.io.Reader(str(source)) as reader:
        osmium.apply(reader, locations, osmium.filter.EmptyTagFilter(), FirstPass())
    flush()
    if cancelled():
        raise net.Cancelled()
    report(0.6)
    # seconda lettura, come BackReferenceWriter (riferimenti completati in C++, tag tolti agli oggetti solo
    # referenziati) ma in un solo passaggio filtrato per id: file identico, senza file temporaneo né zip in Python
    for ident in ways:          # i loro nodi entrano con il completamento, come i riferimenti di add_way
        tracker.add_way(ident)
    tracker.complete_backward_references(str(source), relation_depth=0)
    for ident in nodes:         # dopo il completamento: si aggiungono all'uscita senza seguirne i riferimenti
        tracker.add_node(ident)
    for ident in relations:
        tracker.add_relation(ident)
    report(0.75)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part.pbf')
    if tmp.exists():
        tmp.unlink()
    from osmium._osmium import SimpleWriter

    class Copy(osmium.SimpleHandler):
        def __init__(self, writer):
            super().__init__()
            self.add_node, self.add_way, self.add_relation = writer.add_node, writer.add_way, writer.add_relation

        def node(self, obj):
            self.add_node(obj if obj.id in nodes or not len(obj.tags) else obj.replace(tags={}))

        def way(self, obj):
            self.add_way(obj if obj.id in ways or not len(obj.tags) else obj.replace(tags={}))

        def relation(self, obj):
            self.add_relation(obj if obj.id in relations or not len(obj.tags) else obj.replace(tags={}))

    with SimpleWriter(str(tmp), overwrite=True) as writer:
        with osmium.io.Reader(str(source)) as reader:
            osmium.apply(reader, tracker.id_filter(), Copy(writer))
    tmp.replace(dest)
    return {'tagged_nodes': len(nodes), 'ways': len(ways), 'multipolygons': len(relations)}




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
