import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv('SONAR_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('SONAR_MODELS_DIR', str(ROOT / 'models'))
    yield


@pytest.fixture
def square_city():
    from shapely.geometry import box, mapping
    from sonar_app.places import City
    return City(name='Città di prova', country_code='IT', lat=40.85, lon=14.25, lau_id='000001', gisco_id='IT_000001',
                lau_name='Prova', lau_year=2024, area_km2=12.0, geometry=mapping(box(14.20, 40.82, 14.30, 40.88)))


@pytest.fixture
def model_output(tmp_path):
    """GeoPackage come quello del modello acustico di Sonar: layer feriale/festivo con i campi laeq_* (poligoni)."""
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import box
    cells = [box(14.20 + i * 0.01, 40.82 + j * 0.01, 14.21 + i * 0.01, 40.83 + j * 0.01) for i in range(10) for j in range(6)]
    rng = np.random.default_rng(1)
    path = tmp_path / 'model_h3.gpkg'
    for layer in ('feriale', 'festivo'):
        frame = gpd.GeoDataFrame({'unit_id': [f'c{k}' for k in range(len(cells))]}, geometry=cells, crs=4326).to_crs(32633)
        for band in ('00_06', '06_09', '09_13', '13_17', '17_21', '21_24'):
            values = rng.uniform(38, 82, len(cells))
            values[0] = np.nan
            frame[f'laeq_{band}'] = values
        frame.to_file(path, layer=layer, driver='GPKG')
    return path
