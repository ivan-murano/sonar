import math

import numpy as np
import pandas as pd

from sonar_app.export import health
from sonar_app.model_api import default_model

FIELDS = [{'field': f'laeq_{a:02d}_{b:02d}', 'hours': [a, b]} for a, b in ((0, 6), (6, 9), (9, 13), (13, 17), (17, 21), (21, 24))]


def test_hourly_fields_cover_the_day():
    hours = health.hourly_fields(FIELDS)
    assert hours[0] == 'laeq_00_06' and hours[23] == 'laeq_21_24' and hours[7] == 'laeq_06_09'
    assert health.hourly_fields(FIELDS[:-1]) is None
    assert health.hourly_fields(default_model().output('h3')['map_fields']) is not None


def test_energy_summation_not_arithmetic_mean():
    frame = pd.DataFrame({f['field']: [60.0, 60.0] for f in FIELDS})
    frame.loc[1, 'laeq_00_06'] = 40.0
    values = health.compute(frame, FIELDS, ['lden', 'lnight'])
    # livello costante: Lnight = L, Lden = L + penalità medie
    assert math.isclose(values['lnight'][0], 60.0, abs_tol=0.01)
    assert math.isclose(values['lden'][0], 60 + 10 * math.log10((12 + 4 * 10 ** 0.5 + 8 * 10) / 24), abs_tol=0.01)
    # notte: 2 ore a 60 dB e 6 a 40 dB -> dominano le ore rumorose (energia), non la media dei dB (45)
    expected = 10 * math.log10((2 * 10 ** 6 + 6 * 10 ** 4) / 8)
    assert math.isclose(values['lnight'][1], expected, abs_tol=0.01) and values['lnight'][1] > 54


def test_city_breaks_are_round_regular_steps():
    rng = np.random.default_rng(0)
    values = np.concatenate([np.full(5000, 57.8), rng.uniform(58, 68, 2000)])
    breaks = health.city_breaks(values)
    steps = np.diff(breaks)
    assert np.allclose(steps, steps[0]) and steps[0] in health.STEPS
    assert len(breaks) - 1 <= 8 and breaks[0] <= 57.8 and breaks[-1] >= 67


def test_who_scale_uses_thresholds():
    cfg = {'items': ['lden', 'lnight'], 'scale': 'who', 'clip': [5, 98], 'max_classes': 8}
    styles = health.styles_for([], cfg, default_model().style('laeq'), 'it')
    assert 53 in styles['lden']['breaks'] and 45 in styles['lnight']['breaks']
    for item in styles.values():
        assert len(item['colors']) == len(item['breaks']) + 1


def test_sheet_style_pools_all_panels():
    cfg = {'items': ['lden', 'lnight'], 'scale': 'city', 'clip': [5, 98], 'max_classes': 8}
    rng = np.random.default_rng(2)
    frames = [pd.DataFrame({'lden_ind': rng.uniform(56, 72, 500), 'lnight_ind': rng.uniform(48, 64, 500)}) for _ in range(2)]
    styles = list(health.styles_for(frames, cfg, default_model().style('laeq'), 'it').values())
    shared = health.sheet_style(frames, styles)
    breaks = shared['breaks']
    steps = np.diff(breaks)
    # una sola scala che copre sia Lnight (basso) sia Lden (alto), stessa regola di city_breaks
    assert breaks[0] <= 49 and breaks[-1] >= 71 and len(breaks) - 1 <= 8
    assert np.allclose(steps, steps[0]) and steps[0] in health.STEPS
    assert len(shared['colors']) == len(breaks) + 1
    assert styles[0]['breaks'] != styles[1]['breaks']          # gli stili dei layer restano per indicatore


def test_sheet_style_is_off_with_who_scale():
    cfg = {'items': ['lden', 'lnight'], 'scale': 'who', 'clip': [5, 98], 'max_classes': 8}
    styles = list(health.styles_for([], cfg, default_model().style('laeq'), 'it').values())
    assert health.sheet_style([pd.DataFrame({'lden_ind': [60.0], 'lnight_ind': [50.0]})], styles) is None
