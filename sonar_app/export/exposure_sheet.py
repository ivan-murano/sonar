"""Tavola A4 verticale della popolazione esposta (matplotlib, coordinate in mm dall'angolo in alto a sinistra).

Impaginazione (A4 210 x 297 mm, margini 16 mm):
  intestazione · quattro riquadri (residenti, Lden >= 65, Lnight >= 55, classe Lden più frequente)
  · tabelle Lden e Lnight con barre (feriale piena, festivo chiara) · «come leggere» · note e fonti.
Le soglie OMS restano nel foglio di calcolo: con valori indicativi non sono un titolo sostenibile.
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
VALIDATED_MODELS = {'m3_barcellona'}   # id dei modelli a cui si riferiscono i numeri di accuratezza del testo 'validity'
ROW = 6.2           # altezza di riga delle tabelle (mm)
BAR_W = 66.0        # lunghezza della barra più lunga (mm)


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
    days = result['days'][:2]
    d0 = days[0]
    d1 = days[1] if len(days) > 1 else None

    # ---------------------------------------------------------------- intestazione
    title = text(X0, 25, T['title'].format(city=city), 20, 'bold')
    fig.canvas.draw()                                             # titoli lunghi: si riduce il corpo fino a stare nei margini
    width_mm = title.get_window_extent().width / dpi * 25.4
    if width_mm > X1 - X0:
        title.set_fontsize(max(12.0, 20 * (X1 - X0) / width_mm * 0.98))
    text(X0, 32.5, T['subtitle'].format(model=model_name), 9.5, color=MID)
    rect(X0, 37, X1 - X0, 0.7, ACCENT)

    # ---------------------------------------------------------------- riquadri
    gap, ty, th = 4.0, 44.0, 36.0
    tw = (X1 - X0 - 3 * gap) / 4

    def tile(j, dark=False):
        tx = X0 + j * (tw + gap)
        ax.add_patch(FancyBboxPatch((tx, ty), tw, th, boxstyle='round,pad=0,rounding_size=2.2',
                                    fc=ACCENT if dark else LIGHT, ec='none'))
        return tx + 4.5

    tx = tile(0, dark=True)
    text(tx, ty + 8.5, T['total'], 9, 'bold', color='#ffffff')
    text(tx, ty + 21.5, _fmt(total, language), 18, 'bold', color='#ffffff')
    text(tx, ty + 28.0, 'GHS-POP 2020', 7.2, color=ACCENT_SOFT)

    for j, (key, value, label) in enumerate((('lden', 65, T['high_lden']), ('lnight', 55, T['high_lnight'])), 1):
        tx = tile(j)
        n0 = _threshold(d0, key, value)
        text(tx, ty + 8.5, label, 9, 'bold')
        text(tx, ty + 21.5, _pct(n0, total, language), 18, 'bold', color=ACCENT)
        text(tx, ty + 28.0, f'{_fmt(n0, language)} {T["unit"]} · {d0["short"]}', 7.2, color=MID)
        if d1 is not None:
            text(tx, ty + 32.0, f'{d1["short"]}: {_pct(_threshold(d1, key, value), total, language)}', 7.2, color=MID)

    rows0 = _rows(d0, 'lden')
    top = max(range(len(rows0)), key=lambda i: rows0[i][1])
    tx = tile(3)
    text(tx, ty + 8.5, T['tile_modal'], 9, 'bold')
    text(tx, ty + 21.5, f'{_label(rows0[top][0], language)} dB', 18, 'bold', color=ACCENT)
    text(tx, ty + 28.0, f'{_pct(rows0[top][1], total, language)} {T["of_residents"]} · {d0["short"]}', 7.2, color=MID)
    text(X0, ty + th + 5.5, T['tile_caption'], 7.5, color=SOFT)

    # ---------------------------------------------------------------- tabelle
    cx = {'class': X0 + 4.0, 'bar': X0 + 27.0, 'v': [X0 + 124.0, X0 + 160.0], 'p': [X0 + 141.0, X1 - 1.0]}
    peak = max(max(r[1] for r in _rows(d, k)) for d in days for k in ('lden', 'lnight')) or 1.0

    def table(top_y, key, title):
        rows = _rows(d0, key)
        none_rows = [(_label(('none', None), language), [_none_value(d, key) for d in days])]
        none_rows = [r for r in none_rows if any(v > 0.5 for v in r[1])]
        text(X0, top_y, title, 12, 'bold')
        hy = top_y + 7.5
        text(cx['class'] - 4.0, hy, T['class'], 7.8, 'bold', color=MID)
        for i, d in enumerate(days):
            text(cx['v'][i], hy, d['short'].capitalize(), 7.8, 'bold', color=MID, ha='right')
            text(cx['p'][i], hy, T['share'], 7.8, 'bold', color=MID, ha='right')
        rect(X0, hy + 2.0, X1 - X0, 0.3, RULE)
        y = hy + 2.0
        items = [(_label(r[0], language), [d[key][j][1] for d in days], CLASS_COLORS[min(j, len(CLASS_COLORS) - 1)])
                 for j, r in enumerate(rows)] + [(lab, vals, NONE_COLOR) for lab, vals in none_rows]
        for label, values, color in items:
            mid = y + ROW / 2
            rect(X0, y + 1.1, 2.2, ROW - 2.2, color)                       # chiave del colore di classe
            text(cx['class'], mid, label, 9, 'bold' if values[0] > 0.5 else 'normal',
                 color=INK if any(v > 0.5 for v in values) else SOFT, va='center')
            rect(cx['bar'], mid - 1.9, BAR_W * values[0] / peak, 2.2, color)
            if len(values) > 1:
                rect(cx['bar'], mid + 0.6, BAR_W * values[1] / peak, 1.3, _tint(color, 0.45))
            for i, v in enumerate(values):
                c = INK if v > 0.5 else SOFT
                text(cx['v'][i], mid, _fmt(v, language), 9, color=c, ha='right', va='center')
                text(cx['p'][i], mid, _pct(v, total, language), 9, color=MID if v > 0.5 else SOFT, ha='right', va='center')
            y += ROW
            rect(X0, y, X1 - X0, 0.2, RULE)
        mid = y + ROW / 2
        text(cx['class'], mid, T['total_row'], 9, 'bold', va='center')
        for i, d in enumerate(days):
            text(cx['v'][i], mid, _fmt(total, language), 9, 'bold', ha='right', va='center')   # ogni residente sta in una riga
            text(cx['p'][i], mid, '100%', 9, 'bold', ha='right', va='center', color=MID)
        return y + ROW

    y = table(96.0, 'lden', T['lden_table'])
    # chiave delle barre, una volta sola fra le due tabelle
    ky = y + 5.0
    key_color = CLASS_COLORS[2]
    rect(cx['bar'], ky - 2.2, 7, 2.2, key_color)
    text(cx['bar'] + 9, ky - 0.4, d0['title'], 7.5, color=MID)
    if d1 is not None:
        rect(cx['bar'] + 58, ky - 1.6, 7, 1.3, _tint(key_color, 0.45))
        text(cx['bar'] + 67, ky - 0.4, d1['title'], 7.5, color=MID)
    y = table(ky + 11.0, 'lnight', T['lnight_table'])

    # ---------------------------------------------------------------- come leggere
    note_lines = textwrap.wrap(T['note'], 122)
    foot_top = H - 14.0 - 4.0 * len(note_lines) - 6.0            # le note stanno sopra le fonti
    # numeri di accuratezza solo per il modello a cui si riferiscono (README, docs/MODEL.md), riconosciuto dall'id del manifest
    claim = T['validity'] if model_id in VALIDATED_MODELS else T['validity_generic'].format(model=model_name)
    lines = textwrap.wrap(claim, 124)
    bh = 9.0 + 4.3 * len(lines)
    by = max(y + 8.0, min(foot_top - bh - 7.0, y + 14.0))
    ax.add_patch(FancyBboxPatch((X0, by), X1 - X0, bh, boxstyle='round,pad=0,rounding_size=2.0', fc=LIGHT, ec='none'))
    rect(X0, by, 1.4, bh, ACCENT)
    text(X0 + 6, by + 6.2, T['read_title'], 9, 'bold', color=ACCENT)
    for k, line in enumerate(lines):
        text(X0 + 6, by + 11.0 + 4.3 * k, line, 8, color=INK)

    # ---------------------------------------------------------------- note e fonti
    ny = max(by + bh + 9.0, foot_top + 6.0)
    rect(X0, ny - 5.0, X1 - X0, 0.3, RULE)
    for k, line in enumerate(note_lines):
        text(X0, ny + 4.0 * k, line, 7.2, color=MID)
    text(X0, H - 12, T['sources'], 6.8, color=MID)
    text(X1, H - 12, 'Sonar', 7, 'bold', color=ACCENT, ha='right')
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
