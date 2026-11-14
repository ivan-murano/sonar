"""Indicatori di sintesi per la salute: Lden e Lnight indicativi dalle fasce orarie del modello.

I decibel sono una scala logaritmica: le fasce si combinano sommando l'energia sonora (10^(L/10)), mai
facendo la media aritmetica dei dB. Lden segue la definizione della Direttiva 2002/49/CE (giorno 07-19,
sera 19-23 con +5 dB, notte 23-07 con +10 dB); Lnight è il livello equivalente della notte 23-07.
Il manifest attiva gli indicatori con "indicators" e indica le ore di ogni campo in map_fields[].hours.

Scale di colore:
- "city": classi in dB a passi regolari adattate ai valori della città (passi uguali in dB = rapporti
  di energia uguali), stessa scala per tutte le tavole e i layer della città;
- "who": classi fisse ancorate alle soglie OMS 2018 per il traffico stradale (53 dB Lden, 45 dB Lnight)
  e alle classi di 5 dB della Direttiva. Da usare solo se il modello dichiara valori confrontabili.
"""
from __future__ import annotations

import math

import numpy as np

PERIODS = {'day': list(range(7, 19)), 'evening': list(range(19, 23)), 'night': [23, 0, 1, 2, 3, 4, 5, 6]}
PENALTY_DB = {'day': 0.0, 'evening': 5.0, 'night': 10.0}

INDICATORS = {
    'lden': {'field': 'lden_ind', 'title': {'it': 'Lden indicativo', 'en': 'Indicative Lden'},
             'short': {'it': 'giorno-sera-notte', 'en': 'day-evening-night'}},
    'lnight': {'field': 'lnight_ind', 'title': {'it': 'Lnight indicativo', 'en': 'Indicative Lnight'},
               'short': {'it': 'notte 23–07', 'en': 'night 23–07'}},
}

# Soglie OMS 2018 (Environmental Noise Guidelines for the European Region), traffico stradale.
WHO_THRESHOLD = {'lden': 53, 'lnight': 45}
WHO_BREAKS = {'lden': [45, 50, 53, 55, 60, 65, 70, 75], 'lnight': [40, 45, 50, 55, 60, 65, 70]}
_BELOW = ['#e3f1ea', '#bfe0cf', '#93c9ad']
_ABOVE = ['#fee08b', '#fdae61', '#f46d43', '#d73027', '#a50026', '#5c0a3d']
WHO_COLORS = {'lden': _BELOW + _ABOVE, 'lnight': _BELOW[::2] + _ABOVE}

STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)  # numeri tondi per la legenda
DEFAULT_RAMP = ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026', '#4a0030']


def config(manifest: dict) -> dict | None:
    """Impostazioni degli indicatori dal manifest, o None se il modello non li attiva."""
    spec = manifest.get('indicators')
    if not spec:
        return None
    items = [i for i in spec.get('items', ['lden', 'lnight']) if i in INDICATORS]
    return {'items': items, 'scale': spec.get('scale', 'city'), 'clip': spec.get('clip', [5, 98]),
            'max_classes': int(spec.get('max_classes', 8))} if items else None


def hourly_fields(map_fields: list[dict]) -> list[str] | None:
    """Campo che rappresenta ciascuna delle 24 ore, dalle chiavi hours [inizio, fine) di map_fields."""
    hours: list[str | None] = [None] * 24
    for spec in map_fields:
        span = spec.get('hours')
        if not span:
            continue
        start, end = int(span[0]), int(span[1])
        for h in range(start, end if end > start else end + 24):
            hours[h % 24] = spec['field']
    return hours if all(hours) else None  # type: ignore[return-value]


def compute(frame, map_fields: list[dict], items: list[str]) -> dict:
    """{nome: array} degli indicatori, NaN dove manca una fascia."""
    hours = hourly_fields(map_fields)
    if hours is None:
        raise ValueError('map_fields non coprono le 24 ore (chiave "hours")')
    energy = {f: np.power(10.0, frame[f].to_numpy(dtype=float) / 10.0) for f in set(hours)}
    def total(period, penalty=0.0):
        return sum(energy[hours[h]] for h in PERIODS[period]) * 10 ** (penalty / 10)
    out = {}
    if 'lden' in items:
        out['lden'] = 10 * np.log10(sum(total(p, PENALTY_DB[p]) for p in PERIODS) / 24)
    if 'lnight' in items:
        out['lnight'] = 10 * np.log10(total('night') / len(PERIODS['night']))
    return {k: np.round(v, 2) for k, v in out.items()}


def add_to_frame(frame, map_fields: list[dict], items: list[str]) -> list[str]:
    """Aggiunge i campi lden_ind / lnight_ind al layer (prima di day_type se presente)."""
    values = compute(frame, map_fields, items)
    added = []
    for name, array in values.items():
        field = INDICATORS[name]['field']
        if field in frame.columns:
            frame.drop(columns=field, inplace=True)
        position = frame.columns.get_loc('day_type') if 'day_type' in frame.columns else len(frame.columns) - 1
        frame.insert(position, field, array)
        added.append(field)
    return added


def city_breaks(values, clip=(5, 98), max_classes=8) -> list[float]:
    """Limiti a passi regolari in dB (numeri tondi) tra i percentili clip dei valori della città."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return [40.0, 50.0, 60.0, 70.0]
    lo, hi = np.percentile(values, clip)
    if hi - lo < 1e-6:
        hi = lo + 1
    for step in STEPS:
        if math.ceil(hi / step) - math.floor(lo / step) <= max_classes:
            break
    start, stop = math.floor(lo / step) * step, math.ceil(hi / step) * step
    count = int(round((stop - start) / step))
    return [round(start + i * step, 2) for i in range(count + 1)]


def ramp(colors: list[str], n: int) -> list[str]:
    from matplotlib.colors import LinearSegmentedColormap, to_hex
    cmap = LinearSegmentedColormap.from_list('sonar', colors)
    return [to_hex(cmap(i / max(n - 1, 1))) for i in range(n)]


def styles_for(frames: list, cfg: dict, base_style: dict, language: str) -> dict:
    """{nome: stile} con una sola scala per indicatore su tutti i layer e gli output della città."""
    from ..i18n import pick
    result = {}
    for name in cfg['items']:
        field = INDICATORS[name]['field']
        if cfg['scale'] == 'who':
            breaks, colors = WHO_BREAKS[name], WHO_COLORS[name]
            note = {'it': f'soglia OMS {WHO_THRESHOLD[name]} dB', 'en': f'WHO threshold {WHO_THRESHOLD[name]} dB'}
        else:
            values = np.concatenate([f[field].to_numpy(dtype=float) for f in frames if field in f.columns])
            breaks = city_breaks(values, cfg['clip'], cfg['max_classes'])
            colors = ramp(base_style.get('colors') or DEFAULT_RAMP, len(breaks) + 1)
            note = {'it': 'scala adattata alla città', 'en': 'scale adapted to the city'}
        result[name] = {'title': INDICATORS[name]['title'], 'unit': base_style.get('unit', 'dB(A)'), 'breaks': breaks, 'colors': colors,
                        'no_data_color': base_style.get('no_data_color', '#d5d9dc'), 'scale': cfg['scale'], 'scale_note': note,
                        'field': field, 'label': f'{pick(INDICATORS[name]["title"], language)} ({pick(INDICATORS[name]["short"], language)})'}
    return result


def weighted_quantile(values, weights, q: float) -> float:
    values = np.asarray(values, dtype=float); weights = np.asarray(weights, dtype=float)
    keep = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not keep.any():
        return float('nan')
    order = np.argsort(values[keep])
    v, w = values[keep][order], weights[keep][order]
    cumulative = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(cumulative, q, side='left').clip(0, len(v) - 1)])
