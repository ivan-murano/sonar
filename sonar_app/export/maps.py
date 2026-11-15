"""Tavole PNG: una per output e scenario, con un riquadro per ciascun campo dichiarato in map_fields."""
from __future__ import annotations

import math
from pathlib import Path

from ..i18n import pick

FOOTER = {   # il nome del modello non compare: il modello di Sonar non ha un nome pubblico proprio
    'it': 'Sonar · © OpenStreetMap contributors · © Overture Maps · ESA WorldCover · confini © EuroGeographics',
    'en': 'Sonar · © OpenStreetMap contributors · © Overture Maps · ESA WorldCover · boundaries © EuroGeographics',
}
MEDIAN = {'it': 'mediana {value:.1f} {unit}', 'en': 'median {value:.1f} {unit}'}
NO_VALUES = {'it': 'nessuna stima', 'en': 'no estimate'}


def _colormap(style):
    from matplotlib.colors import BoundaryNorm, ListedColormap
    colors = style['colors']
    cmap = ListedColormap(colors[1:-1]).with_extremes(under=colors[0], over=colors[-1], bad=style.get('no_data_color', '#d5d9dc'))
    return cmap, BoundaryNorm(style['breaks'], cmap.N)


def draw_lines(ax, frame, column, cmap, norm, linewidth, no_data_color):
    """Linee colorate per classe: un solo tracciato per colore invece di un oggetto per segmento.

    Stesso colore e spessore di GeoDataFrame.plot; le classi sono disegnate dalla più bassa alla più alta,
    così i tratti più rumorosi restano sopra. Molto più veloce con centinaia di migliaia di segmenti."""
    import numpy as np
    import shapely
    from matplotlib.colors import to_hex
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    parts, owner = shapely.get_parts(frame.geometry.to_numpy(), return_index=True)
    coords, part_of = shapely.get_coordinates(parts, return_index=True)
    if not len(coords):
        return
    values = frame[column].to_numpy(dtype=float)[owner]
    finite = np.isfinite(values)
    # classe di colore: indice di BoundaryNorm (sotto = -1, sopra = N), -2 per i valori mancanti
    level = np.full(len(parts), -2, dtype=np.int64)
    if finite.any():
        level[finite] = np.asarray(norm(values[finite]), dtype=np.int64)
    first = np.r_[True, part_of[1:] != part_of[:-1]]
    codes_all = np.where(first, MPath.MOVETO, MPath.LINETO).astype(np.uint8)
    vertex_level = level[part_of]
    for value in np.unique(level):                      # dalla classe più bassa alla più alta
        color = to_hex(no_data_color) if value == -2 else to_hex(cmap(int(value)), keep_alpha=False)
        keep = vertex_level == value
        path = MPath(coords[keep], codes_all[keep])
        ax.add_artist(PathPatch(path, fill=False, edgecolor=color, linewidth=linewidth, rasterized=True, capstyle='butt', joinstyle='round'))  # senza ricalcolo dei limiti
    ax.update_datalim([coords.min(0), coords.max(0)])


def render(frame, boundary, fields: list[dict], style: dict, title: str, subtitle: str, path: Path, language: str, model_name: str, dpi=200):
    """frame: GeoDataFrame del layer; boundary: GeoDataFrame del confine; fields: [{'field', 'title'}]."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable
    boundary = boundary.to_crs(frame.crs)
    lines = frame.geom_type.isin(['LineString', 'MultiLineString']).all()
    xmin, ymin, xmax, ymax = boundary.total_bounds
    n = len(fields)
    cols = 3 if n > 4 else max(1, n)
    rows = math.ceil(n / cols)
    width = 15 if cols == 3 else 5 * cols
    aspect = (ymax - ymin) / max(xmax - xmin, 1)
    panel_h = min(max(width / cols * aspect, 2.6), 7)
    cmap, norm = _colormap(style)
    fig, axes = plt.subplots(rows, cols, figsize=(width, rows * panel_h + 1.6), squeeze=False)
    unit = style.get('unit', '')
    for ax, spec in zip(axes.ravel(), fields):
        column = spec['field']
        if lines:
            draw_lines(ax, frame, column, cmap, norm, 0.35, style.get('no_data_color', '#d5d9dc'))
        else:
            frame.plot(column=column, ax=ax, cmap=cmap, norm=norm, rasterized=True, linewidth=0,
                       missing_kwds={'color': style.get('no_data_color', '#d5d9dc')})
        boundary.boundary.plot(ax=ax, color='#222222', linewidth=0.6)
        ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_aspect('equal'); ax.set_axis_off()
        values = frame[column].dropna()
        stat = MEDIAN[language].format(value=values.median(), unit=unit) if len(values) else NO_VALUES[language]
        ax.set_title(f'{pick(spec.get("title"), language) or column}   ·   {stat}', fontsize=11)
    for ax in axes.ravel()[n:]:
        ax.set_axis_off()
    fig.suptitle(title, fontsize=15, fontweight='bold', y=0.995)
    fig.text(0.5, 0.955, subtitle, ha='center', fontsize=10, color='#444444')
    cax = fig.add_axes([0.3, 0.075, 0.4, 0.017])
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', extend='both', ticks=style['breaks'])
    cax.set_title(f'{pick(style.get("title"), language)} {unit}'.strip(), fontsize=10)
    fig.text(0.5, 0.012, FOOTER[language], fontsize=7.5, color='#555555', ha='center')
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.15, wspace=0.03, hspace=0.12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor='white')
    plt.close(fig)
    return path


STAT = {'it': 'mediana {median} · 10% più esposto ≥ {p90} {unit}', 'en': 'median {median} · most exposed 10% ≥ {p90} {unit}'}
NOTE = {
    'it': ('{indicators} calcolati dalle fasce orarie con somma energetica (Direttiva 2002/49/CE: sera +5 dB, notte +10 dB); '
           '{scale}.'),
    'en': ('{indicators} computed from the time bands by energy summation (Directive 2002/49/EC: evening +5 dB, night +10 dB); '
           '{scale}.'),
}
SCALE_NOTE = {
    'city': {'it': 'una sola scala in dB per tutte le mappe della tavola, adattata ai valori della città',
             'en': 'one dB scale for all the maps of the sheet, adapted to the city values'},
    'who': {'it': 'classi ancorate alle soglie OMS 2018 per il traffico stradale (53 dB Lden, 45 dB Lnight)',
            'en': 'classes anchored to the WHO 2018 road traffic thresholds (53 dB Lden, 45 dB Lnight)'},
}

SHARED_LEGEND = {'it': '{unit} · scala unica per le mappe della tavola, adattata alla città',
                 'en': '{unit} · single scale for all the maps of the sheet, adapted to the city'}


def _number(value: float, language: str) -> str:
    text = f'{value:.1f}'
    return text.replace('.', ',') if language == 'it' else text


def render_indicators(layers: list[tuple[str, object]], boundary, indicator_styles: list[dict], title: str, path: Path,
                      language: str, model_name: str, dpi=200):
    """Tavola di sintesi: righe = layer (feriale, festivo), colonne = indicatori (Lden, Lnight).

    Scala "city": una sola scala di colori e una sola legenda, in basso al centro, per tutte le mappe della tavola
    (limiti da health.sheet_style sui valori di tutti i riquadri), così Lden e Lnight si confrontano a vista.
    Scala "who": classi diverse per indicatore, quindi una legenda per colonna.
    Cambia solo il disegno: valori, mediane e percentili dei titoli restano quelli dei layer."""
    import matplotlib
    matplotlib.use('Agg')
    import textwrap

    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable

    from .health import sheet_style, weighted_quantile
    first = layers[0][1]
    boundary = boundary.to_crs(first.crs)
    lines = first.geom_type.isin(['LineString', 'MultiLineString']).all()
    xmin, ymin, xmax, ymax = boundary.total_bounds
    rows, cols = len(layers), len(indicator_styles)
    aspect = (ymax - ymin) / max(xmax - xmin, 1)
    panel_w = 6.2 if cols > 1 else 9
    panel_h = min(max(panel_w * aspect, 3), 8)
    shared = sheet_style([frame for _, frame in layers], indicator_styles)
    fig, axes = plt.subplots(rows, cols, figsize=(panel_w * cols, rows * panel_h + 2.2), squeeze=False)
    for c, style in enumerate(indicator_styles):
        drawing = shared or style            # con la scala unica tutti i riquadri hanno gli stessi cmap e norm
        cmap, norm = _colormap(drawing)
        unit = style.get('unit', '')
        for r, (layer_title, frame) in enumerate(layers):
            ax = axes[r][c]
            column = style['field']
            if lines:
                draw_lines(ax, frame, column, cmap, norm, 0.4, drawing.get('no_data_color', '#d5d9dc'))
            else:
                frame.plot(column=column, ax=ax, cmap=cmap, norm=norm, rasterized=True, linewidth=0,
                           missing_kwds={'color': drawing.get('no_data_color', '#d5d9dc')})
            boundary.boundary.plot(ax=ax, color='#222222', linewidth=0.6)
            ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_aspect('equal'); ax.set_axis_off()
            weights = frame.geometry.length if lines else frame.geometry.area
            values = frame[column]
            if values.notna().any():
                stat = STAT[language].format(median=_number(weighted_quantile(values, weights, 0.5), language),
                                             p90=_number(weighted_quantile(values, weights, 0.9), language), unit=unit)
            else:
                stat = NO_VALUES[language]
            ax.set_title(f'{style["label"]} · {layer_title}\n{stat}', fontsize=10.5)
        if shared is None:                   # scala "who": una legenda per colonna
            left = (c + 0.12) / cols
            cax = fig.add_axes([left, 0.085, 0.76 / cols, 0.016])
            fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', extend='both', ticks=style['breaks'])
            cax.tick_params(labelsize=8)
            cax.set_title(f'{pick(style.get("title"), language)} {unit} · {pick(style.get("scale_note"), language)}'.strip(), fontsize=9)
    if shared is not None:                   # una sola legenda per la tavola, in basso al centro
        cmap, norm = _colormap(shared)
        width = 0.5 if cols > 1 else 0.7
        cax = fig.add_axes([(1 - width) / 2, 0.085, width, 0.018])
        fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', extend='both', ticks=shared['breaks'])
        cax.set_xticklabels([f'{b:g}'.replace('.', ',') if language == 'it' else f'{b:g}' for b in shared['breaks']])
        cax.tick_params(labelsize=9)
        cax.set_title(SHARED_LEGEND[language].format(unit=shared.get('unit', '')).strip(' ·'), fontsize=10)
    names = ' e '.join(pick(s['title'], language) for s in indicator_styles) if language == 'it' else \
        ' and '.join(pick(s['title'], language) for s in indicator_styles)
    fig.suptitle(title, fontsize=15, fontweight='bold', y=0.995)
    note = NOTE[language].format(indicators=names, scale=SCALE_NOTE['city' if shared is not None else indicator_styles[0].get('scale', 'city')][language])
    fig.text(0.5, 0.03, textwrap.fill(note, width=95 * cols if cols > 1 else 120), fontsize=8, color='#444444', ha='center', va='bottom')
    fig.text(0.5, 0.01, FOOTER[language], fontsize=7.5, color='#555555', ha='center')
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.16, wspace=0.03, hspace=0.18)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor='white')
    plt.close(fig)
    return path
