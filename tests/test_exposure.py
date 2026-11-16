"""Popolazione esposta: conservazione dei residenti, foglio di calcolo e tavola A4."""
from __future__ import annotations

import numpy as np
import pytest

gpd = pytest.importorskip('geopandas')
rasterio = pytest.importorskip('rasterio')
openpyxl = pytest.importorskip('openpyxl')
shapely = pytest.importorskip('shapely')

from sonar_app.export import exposure  # noqa: E402


def _case(tmp_path):
    """Griglia 10x10 di pixel da 100 m (EPSG:3035), confine che taglia la griglia, celle esagonali sfalsate."""
    from rasterio.transform import from_origin
    data = np.arange(1, 101, dtype='float32').reshape(10, 10) / 3.0
    raster = tmp_path / 'pop.tif'
    with rasterio.open(raster, 'w', driver='GTiff', width=10, height=10, count=1, dtype='float32', crs='EPSG:3035',
                       transform=from_origin(4_000_000, 2_001_000, 100, 100), nodata=-200) as dst:
        dst.write(data, 1)
    boundary = gpd.GeoDataFrame(geometry=[shapely.box(4_000_000, 2_000_000, 4_000_730, 2_001_000)], crs='EPSG:3035')
    cells, ids = [], []
    for i in range(11):                      # quadrati da 75 m sfalsati sui pixel, coprono tutto il confine senza sovrapporsi
        for j in range(15):
            x, y = 4_000_000 - 25 + i * 75, 2_000_000 - 25 + j * 75
            cells.append(shapely.box(x, y, x + 75, y + 75))
            ids.append(f'8a1e8e2{i:02d}{j:02d}ffff')
    frame = gpd.GeoDataFrame({'unit_id': ids}, geometry=cells, crs='EPSG:3035')
    rng = np.random.default_rng(1)
    frame['lden_ind'] = rng.uniform(50, 78, len(frame)).round(1)
    frame['lnight_ind'] = frame['lden_ind'] - 8
    frame.loc[3, ['lden_ind', 'lnight_ind']] = np.nan
    # popolazione attesa: area di ogni pixel dentro il confine (le celle coprono tutto il confine)
    expected = float(sum(data[r, c] * max(0.0, min(100.0, 730 - c * 100)) / 100 for r in range(10) for c in range(10)))
    return raster, boundary, frame, expected


def test_residents_are_conserved_and_written(tmp_path):
    raster, boundary, frame, expected = _case(tmp_path)
    holiday = frame.copy()
    holiday['lden_ind'] -= 1
    result = exposure.compute([('Giorno feriale scolastico', 'feriale', frame), ('Domenica / festivo', 'festivo', holiday)],
                              raster, boundary)
    assert result['total'] == pytest.approx(expected, rel=1e-6)
    for res in result['residents_by_day']:
        assert res.sum() == pytest.approx(expected, abs=len(res) * 0.0005 + 1e-6)   # arrotondamento a 0,001
    for day in result['days']:
        for key in ('lden', 'lnight'):
            assert sum(v for _, v in day[key]) == pytest.approx(expected, rel=1e-7)
        assert day['lden'][-1][1] > 0                                    # la cella senza stima ha residenti

    xlsx = exposure.write_xlsx(tmp_path / 'esposti.xlsx', result, 'Prova', 'modello acustico di Sonar', 'it')
    wb = openpyxl.load_workbook(xlsx)
    cells = wb['Celle H3']
    assert cells['A2'].value == frame['unit_id'].iloc[0]                # identificativo H3, non il numero di riga
    assert sum(r[1].value for r in cells.iter_rows(min_row=2)) == pytest.approx(expected, abs=len(frame) * 0.005)

    for language in ('it', 'en'):
        name = {'it': 'modello acustico di Sonar', 'en': 'Sonar acoustic model'}[language]      # come pick(manifest['name'])
        png = exposure.render_png(tmp_path / f'esposti_{language}.png', result, 'Prova', name, language,
                                  model_id='m3_barcellona')
        assert png.stat().st_size > 50_000


def test_share_formatting():
    assert exposure._pct(0, 100, 'it') == '0,0%'
    assert exposure._pct(1, 10_000, 'it') == '< 0,1%'
    assert exposure._pct(1, 8, 'en') == '12.5%'


def test_sheet_shows_only_exposure_numbers(tmp_path, monkeypatch):
    """La tavola A4 riporta solo le persone per fascia: niente testi sul modello o sulla sua accuratezza."""
    from matplotlib.figure import Figure
    raster, boundary, frame, _ = _case(tmp_path)
    result = exposure.compute([('Giorno feriale scolastico', 'feriale', frame)], raster, boundary)
    seen = []
    original = Figure.savefig
    def savefig(self, *args, **kwargs):
        seen.append([t.get_text() for ax in self.axes for t in ax.texts])
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Figure, 'savefig', savefig)
    exposure.render_png(tmp_path / 'a.png', result, 'Prova', 'modello acustico di Sonar', 'it', model_id='m3_barcellona')
    exposure.render_png(tmp_path / 'c.png', result, 'Prova', 'Altro modello', 'en')
    joined = [' '.join(texts) for texts in seen]
    assert all('3,6' not in j and '3.6' not in j and 'modello' not in j.lower() and 'model ' not in j.lower() for j in joined)
    assert 'Quante persone vivono' in joined[0] and 'How many people live' in joined[1]
    assert all('Sonar' in texts for texts in seen)
