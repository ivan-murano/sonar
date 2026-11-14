"""Tavole PNG: una per output e scenario, con un riquadro per ciascun campo dichiarato in map_fields."""
from __future__ import annotations

import math
from pathlib import Path

from ..i18n import pick

FOOTER = {
    'it': 'Sonar · {model} · stima sperimentale · © OpenStreetMap contributors · © Overture Maps · ESA WorldCover · confini © EuroGeographics',
    'en': 'Sonar · {model} · experimental estimate · © OpenStreetMap contributors · © Overture Maps · ESA WorldCover · boundaries © EuroGeographics',
}
MEDIAN = {'it': 'mediana {value:.1f} {unit}', 'en': 'median {value:.1f} {unit}'}
NO_VALUES = {'it': 'nessuna stima', 'en': 'no estimate'}


def _colormap(style):
    from matplotlib.colors import BoundaryNorm, ListedColormap
    colors = style['colors']
    cmap = ListedColormap(colors[1:-1]).with_extremes(under=colors[0], over=colors[-1], bad=style.get('no_data_color', '#d5d9dc'))
    return cmap, BoundaryNorm(style['breaks'], cmap.N)


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
        kwargs = dict(column=column, ax=ax, cmap=cmap, norm=norm, rasterized=True, missing_kwds={'color': style.get('no_data_color', '#d5d9dc')})
        frame.plot(linewidth=0.35 if lines else 0, **kwargs)
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
    fig.text(0.5, 0.012, FOOTER[language].format(model=model_name), fontsize=7.5, color='#555555', ha='center')
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.15, wspace=0.03, hspace=0.12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor='white')
    plt.close(fig)
    return path
