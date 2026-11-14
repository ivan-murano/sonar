from pathlib import Path

import pytest
from shapely.geometry import box, mapping

from sonar_app import places
from sonar_app.providers import area_bounds, osm, worldcover


def test_area_bounds_buffer(square_city):
    w, s, e, n = area_bounds(square_city, 0)
    w2, s2, e2, n2 = area_bounds(square_city, 1000)
    assert w2 < w and s2 < s and e2 > e and n2 > n
    assert abs((n2 - n) - 1000 / 111_000) < 0.002


def test_worldcover_tiles():
    assert worldcover.tiles((14.12, 40.78, 14.37, 40.92)) == ['N39E012']
    assert set(worldcover.tiles((-0.5, 50.9, 0.5, 51.2))) == {'N48W003', 'N48E000', 'N51W003', 'N51E000'}


def test_geofabrik_smallest_covering_extract():
    feature = lambda id_, b: {'type': 'Feature', 'geometry': mapping(box(*b)), 'properties': {'id': id_, 'urls': {'pbf': f'https://x/{id_}.osm.pbf'}}}
    index = {'features': [feature('europe', (-30, 30, 50, 75)), feature('italy', (6, 36, 19, 47.5)), feature('sud', (13, 37, 19, 42)),
                          feature('nord-ovest', (6, 43, 10, 46.5))]}
    assert osm.select_extract(index, box(14.1, 40.7, 14.4, 41.0))['id'] == 'sud'
    with pytest.raises(LookupError):
        osm.select_extract(index, box(-60, 0, -59, 1))


def test_clip_pbf_keeps_complete_ways(tmp_path):
    import osmium
    source = tmp_path / 'in.osm.pbf'
    with osmium.SimpleWriter(str(source)) as writer:
        writer.add_node(osmium.osm.mutable.Node(id=1, location=(14.25, 40.85), tags={'amenity': 'cafe'}))
        writer.add_node(osmium.osm.mutable.Node(id=2, location=(14.26, 40.85)))
        writer.add_node(osmium.osm.mutable.Node(id=3, location=(15.50, 41.50)))          # fuori riquadro
        writer.add_node(osmium.osm.mutable.Node(id=4, location=(15.60, 41.60), tags={'shop': 'bakery'}))  # fuori
        writer.add_way(osmium.osm.mutable.Way(id=10, nodes=[1, 2, 3], tags={'highway': 'primary'}))      # attraversa il bordo
        writer.add_way(osmium.osm.mutable.Way(id=11, nodes=[3, 4], tags={'highway': 'residential'}))      # tutta fuori
    dest = tmp_path / 'out.osm.pbf'
    counts = osm.clip_pbf(source, dest, (14.2, 40.8, 14.3, 40.9))
    assert counts['ways'] == 1 and counts['tagged_nodes'] == 1
    ways, nodes = {}, {}
    for obj in osmium.FileProcessor(str(dest)):
        (ways if obj.is_way() else nodes)[obj.id] = obj
    assert set(ways) == {10} and {1, 2, 3} <= set(nodes) and 4 not in nodes


def test_nominatim_results_are_filtered(monkeypatch):
    sample = [
        {'name': 'Napoli', 'lat': '40.8358', 'lon': '14.2488', 'category': 'boundary', 'addresstype': 'city', 'importance': 0.8,
         'address': {'city': 'Napoli', 'state': 'Campania', 'country': 'Italia', 'country_code': 'it'}},
        {'name': 'Napoli', 'lat': '40.8360', 'lon': '14.2490', 'category': 'place', 'addresstype': 'city', 'importance': 0.7,
         'address': {'state': 'Campania', 'country': 'Italia', 'country_code': 'it'}},
        {'name': 'Via Napoli', 'lat': '45.0', 'lon': '9.0', 'category': 'highway', 'addresstype': 'road', 'importance': 0.3, 'address': {}},
    ]
    monkeypatch.setattr(places.net, 'get_json', lambda url, params=None, timeout=None: sample)
    monkeypatch.setattr(places, '_respect_rate_limit', lambda: None)
    found = places.search('Napoli')
    assert len(found) == 1 and found[0].label == 'Napoli, Campania, Italia' and found[0].country_code == 'IT'


def test_lau_feature_parsing_and_catalog():
    candidate = places.Candidate('Napoli', 'Napoli, Italia', 40.85, 14.25, 'IT', 'city')
    feature = {'properties': {'GISCO_ID': 'IT_063049', 'LAU_ID': '063049', 'LAU_NAME': 'Napoli', 'CNTR_CODE': 'IT', 'POP_2024': 909048},
               'geometry': mapping(box(14.13, 40.79, 14.35, 40.92))}
    city = places._from_feature(feature, candidate, 2024, 'test')
    assert city.gisco_id == 'IT_063049' and city.population == 909048 and 200 < city.area_km2 < 500
    listing = {'gpkg': {'LAU_RG_01M_2024_3035.gpkg': 'gpkg/LAU_RG_01M_2024_3035.gpkg', 'LAU_RG_01M_2024_4326.gpkg': 'gpkg/LAU_RG_01M_2024_4326.gpkg'}}
    assert places._find_lau_file(listing, 2024).endswith('/gpkg/LAU_RG_01M_2024_4326.gpkg')
