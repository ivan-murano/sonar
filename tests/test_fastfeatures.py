import sys
import types

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from sonar_app import fastfeatures
from reference_spatial_features import SpatialFeatureContext  # stessa cartella dei test

GROUPS = fastfeatures.GROUPS


def synthetic_city(seed=0, n_roads=400, n_buildings=900, n_pois=1500, n_points=300):
    rng = np.random.default_rng(seed)
    size = 3000.0
    roads = []
    for i in range(n_roads):
        start = rng.uniform(0, size, 2)
        steps = rng.normal(0, 60 if i % 10 else 400, (rng.integers(1, 8), 2))  # alcune strade lunghe
        roads.append(LineString(np.vstack([start, start + np.cumsum(steps, axis=0)])))
    kinds = rng.choice(['primary', 'residential', 'footway', 'secondary_link', 'service', 'track'], n_roads)
    buildings = []
    for i in range(n_buildings):
        c = rng.uniform(0, size, 2); w, h = rng.uniform(5, 40 if i % 25 else 250, 2)
        outer = [(c[0] - w, c[1] - h), (c[0] + w, c[1] - h), (c[0] + w, c[1] + h), (c[0], c[1] + 1.4 * h), (c[0] - w, c[1] + h)]
        if i % 7 == 0:   # cortile interno
            buildings.append(Polygon(outer, [[(c[0] - w / 3, c[1] - h / 3), (c[0] + w / 3, c[1] - h / 3), (c[0], c[1] + h / 3)]]))
        elif i % 11 == 0:
            buildings.append(MultiPolygon([Polygon(outer), Polygon([(c[0] + 2 * w, c[1]), (c[0] + 3 * w, c[1]), (c[0] + 2.5 * w, c[1] + h)])]))
        else:
            buildings.append(Polygon(outer))
    pois = gpd.GeoDataFrame({'group': rng.choice(GROUPS + ['ignoto'], n_pois),
                             'opening_hours': np.where(rng.random(n_pois) < 0.4, 'Mo-Fr 09:00-18:00', None)},
                            geometry=gpd.points_from_xy(*rng.uniform(0, size, (2, n_pois))), crs=32633)
    pts = list(gpd.points_from_xy(*rng.uniform(300, size - 300, (2, n_points - 40))))
    pts += [Point(np.asarray(r.coords)[0]) for r in roads[:20]]            # ricevitori sopra un vertice stradale
    pts += [b.representative_point() for b in buildings[:20]]             # ricevitori dentro edifici
    road_frame = gpd.GeoDataFrame({'highway': kinds}, geometry=roads, crs=32633)
    build_frame = gpd.GeoDataFrame(geometry=buildings, crs=32633)
    return road_frame, build_frame, pois, pois.iloc[::2].copy(), gpd.GeoSeries(pts, crs=32633)


def test_same_features_as_model_reference():
    roads, buildings, osm, places, points = synthetic_city()
    expected = SpatialFeatureContext(roads, buildings, osm, places).compute(points)
    got = fastfeatures.FastSpatialFeatureContext(roads, buildings, osm, places).compute(points)
    assert got.columns.tolist() == expected.columns.tolist()
    np.testing.assert_allclose(got.to_numpy(float), expected.to_numpy(float), rtol=1e-10, atol=1e-7)
    counts = [c for c in expected.columns if not c.startswith(('road_', 'building_'))]
    assert (got[counts].to_numpy() == expected[counts].to_numpy()).all()


@pytest.mark.parametrize('seed', [1, 2])
def test_other_layouts_and_radii(seed):
    roads, buildings, osm, places, points = synthetic_city(seed, n_points=120)
    expected = SpatialFeatureContext(roads, buildings, osm, places).compute(points, radii=(50, 300))
    got = fastfeatures.FastSpatialFeatureContext(roads, buildings, osm, places).compute(points, radii=(50, 300))
    np.testing.assert_allclose(got.to_numpy(float), expected.to_numpy(float), rtol=1e-10, atol=1e-7)


def test_parallel_static_features_with_cache(tmp_path, monkeypatch):
    roads, buildings, osm, places, points = synthetic_city(3, n_points=250)
    receivers = gpd.GeoDataFrame({'unit_id': [f'u{i}' for i in range(len(points))]}, geometry=points, crs=32633)
    legacy = types.ModuleType('sonar.legacy')
    legacy.reference_features_function = lambda: (lambda pts, r, b, o, p, cfg: SpatialFeatureContext(r, b, o, p).compute(pts))
    monkeypatch.setitem(sys.modules, 'sonar', types.ModuleType('sonar'))
    monkeypatch.setitem(sys.modules, 'sonar.legacy', legacy)
    lines = []
    spatial, diff = fastfeatures.compute_static_features(receivers, roads, buildings, osm, places, {}, tmp_path / 'cache', workers=2, chunk=60, log=lines.append)
    expected = SpatialFeatureContext(roads, buildings, osm, places).compute(points)
    assert spatial.unit_id.tolist() == receivers.unit_id.tolist() and diff < 1e-7
    np.testing.assert_allclose(spatial[expected.columns].to_numpy(float), expected.to_numpy(float), rtol=1e-10, atol=1e-7)
    assert any('processi' in line for line in lines) and len(list((tmp_path / 'cache').glob('*.parquet'))) == 5
    # ripresa: i blocchi già calcolati non si ricalcolano
    again, _ = fastfeatures.compute_static_features(receivers, roads, buildings, osm, places, {}, tmp_path / 'cache', workers=2, chunk=60, log=lines.append)
    assert any('ripresi' in line for line in lines) and again.equals(spatial)


def test_default_workers_respects_override(monkeypatch):
    monkeypatch.setenv('SONAR_FEATURE_WORKERS', '3')
    assert fastfeatures.default_workers() == 3
    monkeypatch.delenv('SONAR_FEATURE_WORKERS')
    assert 1 <= fastfeatures.default_workers() <= 8


def test_numpy_path_matches_compiled_path(monkeypatch):
    roads, buildings, osm, places, points = synthetic_city(4, n_points=150)
    expected = SpatialFeatureContext(roads, buildings, osm, places).compute(points)
    monkeypatch.setenv('SONAR_NUMBA', '0')
    numpy_path = fastfeatures.FastSpatialFeatureContext(roads, buildings, osm, places)
    assert numpy_path.kernels is None
    np.testing.assert_allclose(numpy_path.compute(points).to_numpy(float), expected.to_numpy(float), rtol=1e-10, atol=1e-7)


def test_speculative_keys_are_deterministic():
    from sonar_app import speculative
    roads, buildings, osm, places, points = synthetic_city(5, n_points=60)
    places = places.assign(unit_id=[f'p{i}' for i in range(len(places))])
    osm = osm.assign(unit_id=[f'o{i}' for i in range(len(osm))])
    a = speculative.programs_key(places.copy(), osm.copy(), {'x': [1, 2]}, 32633)
    b = speculative.programs_key(places.copy(deep=True), osm.copy(deep=True), {'x': [1, 2]}, 32633)
    c = speculative.programs_key(places.iloc[1:], osm, {'x': [1, 2]}, 32633)
    assert a == b and a != c
