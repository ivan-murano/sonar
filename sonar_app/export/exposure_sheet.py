"""Tavola A4 verticale della popolazione esposta (matplotlib, coordinate in mm dall'angolo in alto a sinistra).

Una pagina da leggere a colpo d'occhio: quante persone vivono in ogni fascia di rumore.
Impaginazione (A4 210 x 297 mm, margini 16 mm): città e sottotitolo · tre numeri (residenti, oltre 65 dB nella
giornata, oltre 55 dB di notte) · fasce della Direttiva 2002/49/CE per la giornata (Lden) e per la notte (Lnight),
giorno feriale · fonti. Dettagli (giorno festivo, soglie OMS, metodo) restano nel foglio di calcolo.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from .exposure import TXT, _fmt, _label, _pct

W, H = 210.0, 297.0
X0, X1 = 16.0, W - 16.0
INK, MID, SOFT, LIGHT, RULE = '#1a1a1a', '#5f6368', '#8a8f96', '#f2f4f7', '#dcdfe3'
ACCENT, ACCENT_SOFT = '#1F4E79', '#dbe6f1'
# classi: verde sotto la prima classe della Direttiva, poi dal giallo al bordeaux; grigio per «senza stima»
CLASS_COLORS = ['#93c9ad', '#fee08b', '#fdae61', '#f46d43', '#d73027', '#a50026']
NONE_COLOR = '#c4c7cc'
ROW = 8.0           # altezza di riga delle tabelle (mm)
BAR_W = 82.0        # lunghezza della barra più lunga (mm)


def _font_family(matplotlib):
    names = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for name in ('Arial', 'Helvetica', 'Liberation Sans'):
        if name in names:
            return name
    return 'DejaVu Sans'


def _tint(hex_color, alpha):
    """Colore schiarito verso il bianco (alpha = quota del colore pieno)."""
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return '#%02x%02x%02x' % tuple(round(255 - (255 - c) * alpha) for c in (r, g, b))


def _rows(day, key):
    """Righe della tabella: classi della Direttiva, più «senza stima» solo se ci sono residenti senza stima."""
    rows = list(day[key])
    if rows and isinstance(rows[-1][0], tuple) and rows[-1][0][0] == 'none':
        rows = rows[:-1]
    return rows


def _none_value(day, key):
    last = day[key][-1]
    return last[1] if isinstance(last[0], tuple) and last[0][0] == 'none' else 0.0


def _threshold(day, key, value):
    for k, v, _kind, n in day['thresholds']:
        if k == key and v == value:
            return n
    return 0.0


def render(path: Path, result: dict, city: str, model_name: str, language: str, dpi: int = 220, model_id: str | None = None) -> Path:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle
    T = TXT[language]
    fam = _font_family(matplotlib)
    fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis('off')

    def text(x, y, s, size=9, weight='normal', color=INK, ha='left', va='baseline', **kw):
        return ax.text(x, y, s, fontsize=size, fontweight=weight, color=color, ha=ha, va=va, family=fam, **kw)

    def rect(x, y, w, h, color, **kw):
        if w > 0 and h > 0:
            ax.add_patch(Rectangle((x, y), w, h, color=color, lw=0, **kw))

    total = result['total']
    d0 = result['days'][0]

    # ---------------------------------------------------------------- intestazione
    title = text(X0, 27, city, 26, 'bold')
    fig.canvas.draw()                                             # nomi lunghi: si riduce il corpo fino a stare nei margini
    width_mm = title.get_window_extent().width / dpi * 25.4
    if width_mm > X1 - X0:
        title.set_fontsize(max(14.0, 26 * (X1 - X0) / width_mm * 0.98))
    text(X0, 36, T['sheet_sub'], 12.5, color=MID)
    rect(X0, 41, X1 - X0, 0.8, ACCENT)

    # ---------------------------------------------------------------- tre numeri
    gap, ty, th = 5.0, 49.0, 34.0
    tw = (X1 - X0 - 2 * gap) / 3
    tiles = [(T['tile_total'], _fmt(total, language), T['tile_total_sub'], True),
             (T['tile_day'], _fmt(_threshold(d0, 'lden', 65), language), f"{_pct(_threshold(d0, 'lden', 65), total, language)} {T['of_residents']}", False),
             (T['tile_night'], _fmt(_threshold(d0, 'lnight', 55), language), f"{_pct(_threshold(d0, 'lnight', 55), total, language)} {T['of_residents']}", False)]
    for j, (label, big, small, dark) in enumerate(tiles):
        tx = X0 + j * (tw + gap)
        ax.add_patch(FancyBboxPatch((tx, ty), tw, th, boxstyle='round,pad=0,rounding_size=2.4', fc=ACCENT if dark else LIGHT, ec='none'))
        fg, sub = ('#ffffff', ACCENT_SOFT) if dark else (INK, MID)
        text(tx + 5, ty + 9, label, 9.5, 'bold', color=fg)
        text(tx + 5, ty + 23, big, 21, 'bold', color=fg if dark else ACCENT)
        text(tx + 5, ty + 29.5, small, 8.5, color=sub)

    # ---------------------------------------------------------------- fasce
    cx = {'class': X0 + 5.0, 'bar': X0 + 34.0, 'v': X1 - 22.0, 'p': X1 - 1.0}
    peak = max(max(r[1] for r in _rows(d0, k)) for k in ('lden', 'lnight')) or 1.0

    def table(top_y, key, title, hint):
        rows = _rows(d0, key)
        text(X0, top_y, title, 14, 'bold')
        text(X0, top_y + 6, hint, 9, color=MID)
        hy = top_y + 14.5
        text(cx['class'] - 5.0, hy, T['col_band'], 8.5, 'bold', color=MID)
        text(cx['v'], hy, T['col_people'], 8.5, 'bold', color=MID, ha='right')
        text(cx['p'], hy, T['col_share'], 8.5, 'bold', color=MID, ha='right')
        rect(X0, hy + 2.2, X1 - X0, 0.3, RULE)
        y = hy + 2.2
        items = [(_band(r[0], language), r[1], CLASS_COLORS[min(j, len(CLASS_COLORS) - 1)]) for j, r in enumerate(rows)]
        none_v = _none_value(d0, key)
        if none_v > 0.5:
            items.append((_label(('none', None), language), none_v, NONE_COLOR))
        for label, value, color in items:
            mid = y + ROW / 2
            rect(X0, y + 1.4, 2.6, ROW - 2.8, color)
            text(cx['class'], mid, label, 10.5, 'bold' if value > 0.5 else 'normal', color=INK if value > 0.5 else SOFT, va='center')
            rect(cx['bar'], mid - 1.8, BAR_W * value / peak, 3.6, color)
            text(cx['v'], mid, _fmt(value, language), 10.5, color=INK if value > 0.5 else SOFT, ha='right', va='center')
            text(cx['p'], mid, _pct(value, total, language), 10.5, color=MID if value > 0.5 else SOFT, ha='right', va='center')
            y += ROW
            rect(X0, y, X1 - X0, 0.2, RULE)
        return y

    y = table(102.0, 'lden', T['tbl_day'], T['tbl_day_hint'].format(day=d0['title'].lower()))
    table(y + 16.0, 'lnight', T['tbl_night'], T['tbl_night_hint'].format(day=d0['title'].lower()))

    # ---------------------------------------------------------------- fonti
    rect(X0, H - 20, X1 - X0, 0.3, RULE)
    text(X0, H - 14, T['sheet_bands'], 7.2, color=MID)
    text(X0, H - 10, T['sources'], 6.8, color=MID)
    text(X1, H - 10, 'Sonar', 7.5, 'bold', color=ACCENT, ha='right')
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _band(label, language):
    """Fascia leggibile: «meno di 55», «55–59», «75 e oltre»."""
    T = TXT[language]
    if isinstance(label, tuple):
        return T['band_below'].format(v=label[1]) if label[0] == 'below' else T['none']
    if label.startswith('≥'):
        return T['band_above'].format(v=label.lstrip('≥ ').strip())
    return label
