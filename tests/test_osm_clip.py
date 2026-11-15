import osmium
import pytest

from sonar_app.providers import osm as provider


def synthetic_pbf(path):
    """Nodi con e senza tag dentro e fuori dal riquadro, way a cavallo, way fuori, multipoligono."""
    with osmium.SimpleWriter(str(path)) as writer:
        coords = {}
        node_id = 1
        for i in range(30):
            for j in range(30):
                lon, lat = 10 + i * 0.01, 45 + j * 0.01
                tags = {'amenity': 'cafe'} if (i + j) % 7 == 0 else {}
                writer.add_node(osmium.osm.mutable.Node(id=node_id, location=(lon, lat), tags=tags, version=1))
                coords[(i, j)] = node_id
                node_id += 1
        ways = []
        way_id = 1
        for i in range(0, 29, 2):     # strade orizzontali lunghe, molte attraversano il riquadro
            refs = [coords[(k, i)] for k in range(30)]
            writer.add_way(osmium.osm.mutable.Way(id=way_id, nodes=refs, tags={'highway': 'residential'}, version=1)); ways.append(way_id); way_id += 1
        for i in range(0, 28, 3):     # edifici piccoli ovunque
            for j in range(0, 28, 3):
                ring = [coords[(i, j)], coords[(i + 1, j)], coords[(i + 1, j + 1)], coords[(i, j + 1)], coords[(i, j)]]
                writer.add_way(osmium.osm.mutable.Way(id=way_id, nodes=ring, tags={'building': 'yes'}, version=1)); ways.append(way_id); way_id += 1
        untagged = way_id
        writer.add_way(osmium.osm.mutable.Way(id=untagged, nodes=[coords[(0, 0)], coords[(29, 29)]], tags={}, version=1))
        writer.add_relation(osmium.osm.mutable.Relation(id=1, members=[('w', ways[3], 'outer'), ('w', untagged, 'inner')],
                                                          tags={'type': 'multipolygon', 'landuse': 'grass'}, version=1))
        writer.add_relation(osmium.osm.mutable.Relation(id=2, members=[('w', ways[-1], 'outer')], tags={'type': 'route'}, version=1))
        # relazioni annidate e nodo con tag fuori dal riquadro: completamento dei riferimenti e tag tolti
        writer.add_relation(osmium.osm.mutable.Relation(id=3, members=[('w', ways[4], 'outer'), ('r', 4, ''), ('n', coords[(26, 23)], 'label')],
                                                          tags={'type': 'multipolygon', 'leisure': 'park'}, version=1))
        writer.add_relation(osmium.osm.mutable.Relation(id=4, members=[('w', ways[-1], ''), ('r', 5, ''), ('n', coords[(28, 28)], '')],
                                                          tags={'type': 'collection'}, version=1))
        writer.add_relation(osmium.osm.mutable.Relation(id=5, members=[('n', coords[(1, 1)], ''), ('w', ways[0], '')],
                                                          tags={'type': 'site', 'name': 'x'}, version=1))


def test_fast_clip_identical_to_simple(tmp_path):
    src = tmp_path / 'regione.osm.pbf'
    synthetic_pbf(src)
    bounds = (10.05, 45.05, 10.17, 45.16)
    simple = provider.clip_pbf_simple(src, tmp_path / 'semplice.osm.pbf', bounds)
    fast = provider._clip_pbf_fast(src, tmp_path / 'veloce.osm.pbf', bounds, lambda: False, lambda f: None)
    assert fast == simple and simple['ways'] > 0 and simple['tagged_nodes'] > 0
    assert (tmp_path / 'semplice.osm.pbf').read_bytes() == (tmp_path / 'veloce.osm.pbf').read_bytes()
