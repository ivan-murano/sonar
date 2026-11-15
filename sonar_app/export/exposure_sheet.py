"""Tavola A4 verticale della popolazione esposta (matplotlib, coordinate in mm dall'angolo in alto a sinistra)."""
from __future__ import annotations

from pathlib import Path

from .exposure import TXT, _fmt, _label, _pct

W, H = 210.0, 297.0
INK, MID, LIGHT, RULE = '#1a1a1a', '#6b6b6b', '#f3f5f8', '#d9d9d9'
ACCENT = '#1F4E79'
# classi: verdi sotto la prima soglia della Direttiva, poi dal giallo al viola come le tavole Lden/Lnight
CLASS_COLORS = ['#93c9ad', '#fee08b', '#fdae61', '#f46d43', '#d73027', '#a50026', '#cfcfcf']


def render(path: Path, result: dict, city: str, model_name: str, language: str, dpi: int = 220) -> Path:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle
    T = TXT[language]
    fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis('off')
    fam = {'family': 'DejaVu Sans'}
    for name in ('Arial', 'Helvetica', 'Liberation Sans'):
        if any(name in f.name for f in matplotlib.font_manager.fontManager.ttflist):
            fam = {'family': name}; break

    def text(x, y, s, size=9, weight='normal', color=INK, ha='left', va='baseline', **kw):
        ax.text(x, y, s, fontsize=size, fontweight=weight, color=color, ha=ha, va=va, **fam, **kw)

    total = result['total']
    days = result['days']
    x0, x1 = 16.0, W - 16.0
    # intestazione
    text(x0, 24, T['title'].format(city=city), 19, 'bold')
    text(x0, 31.5, T['subtitle'].format(model=model_name), 9.5, color=MID)
    ax.add_patch(Rectangle((x0, 36), x1 - x0, 0.6, color=ACCENT, lw=0))

    # numeri chiave: totale e tre soglie, per il primo giorno (feriale); il secondo in piccolo
    tiles = [('total', None)] + [(k, i) for i, k in enumerate(['who_lden', 'who_lnight', 'end_lden'])]
    gap, tw, ty, th = 4.0, (x1 - x0 - 3 * 4.0) / 4, 42.0, 34.0
    th_index = {('lden', 53): 0, ('lnight', 45): 1, ('lden', 55): 2}
    for j, (key, idx) in enumerate(tiles):
        tx = x0 + j * (tw + gap)
        ax.add_patch(FancyBboxPatch((tx, ty), tw, th, boxstyle='round,pad=0,rounding_size=2.2', fc=LIGHT if j else ACCENT, ec='none'))
        main = '#ffffff' if j == 0 else INK
        if key == 'total':
            text(tx + 4, ty + 8, T['total'], 9, 'bold', color='#ffffff')
            text(tx + 4, ty + 21, _fmt(total, language), 17, 'bold', color='#ffffff')
            text(tx + 4, ty + 28.5, 'GHS-POP 2020', 7.5, color='#dbe6f1')
        else:
            value = days[0]['thresholds'][idx][3]
            text(tx + 4, ty + 8, T[key], 9, 'bold', color=main)
            text(tx + 4, ty + 21, _pct(value, total, language), 17, 'bold', color=ACCENT)
            text(tx + 4, ty + 28.5, f'{_fmt(value, language)} · {days[0]["short"]}', 7.5, color=MID)
    text(x0 + tw + gap, ty + th + 5.5, f'{T["who"]} · {T["end"]}', 7.5, color=MID)

    # tabelle con barre
    def table(top, key, title):
        rows = days[0][key]
        text(x0, top, title, 12, 'bold')
        cx = {'class': x0, 'bar': x0 + 30, 'v': [x0 + 120, x0 + 158], 'p': [x0 + 138, x0 + 176]}
        hy = top + 8
        text(cx['class'], hy, T['class'], 8, 'bold', color=MID)
        for i, d in enumerate(days[:2]):
            text(cx['v'][i], hy, d['short'].capitalize(), 8, 'bold', color=MID, ha='right')
            text(cx['p'][i], hy, T['share'], 8, 'bold', color=MID, ha='right')
        ax.add_patch(Rectangle((x0, hy + 2), x1 - x0, 0.3, color=RULE, lw=0))
        bar_w = 62.0
        peak = max(max(r[1] for r in d[key]) for d in days[:2]) or 1
        y = hy + 3
        for j in range(len(rows)):
            y += 6.6
            color = CLASS_COLORS[j] if j < len(rows) - 1 else CLASS_COLORS[-1]
            label = _label(rows[j][0], language)
            text(cx['class'], y, label, 9, 'bold' if j else 'normal')
            for i, d in enumerate(days[:2]):
                v = d[key][j][1]
                w = bar_w * v / peak
                if i == 0:
                    ax.add_patch(Rectangle((cx['bar'], y - 4.1), w, 2.4, color=color, lw=0))
                else:
                    ax.add_patch(Rectangle((cx['bar'], y - 1.5), w, 1.4, fc='none', ec=color, lw=0.8))
                text(cx['v'][i], y, _fmt(v, language), 9, ha='right')
                text(cx['p'][i], y, _pct(v, total, language), 9, ha='right', color=MID)
            ax.add_patch(Rectangle((x0, y + 2.2), x1 - x0, 0.2, color=RULE, lw=0))
        y += 6.6
        text(cx['class'], y, T['total_row'], 9, 'bold')
        for i, d in enumerate(days[:2]):
            text(cx['v'][i], y, _fmt(sum(r[1] for r in d[key]), language), 9, 'bold', ha='right')
            text(cx['p'][i], y, '100%' if language == 'en' else '100%', 9, 'bold', ha='right', color=MID)
        # chiave delle barre
        ly = y + 7
        ax.add_patch(Rectangle((cx['bar'], ly - 2.6), 6, 2.4, color=CLASS_COLORS[2], lw=0))
        text(cx['bar'] + 8, ly - 0.6, days[0]['title'], 7.5, color=MID)
        if len(days) > 1:
            ax.add_patch(Rectangle((cx['bar'] + 56, ly - 1.8), 6, 1.4, fc='none', ec=CLASS_COLORS[2], lw=0.8))
            text(cx['bar'] + 64, ly - 0.6, days[1]['title'], 7.5, color=MID)
        return ly + 6

    y = table(94, 'lden', T['lden_table'])
    y = table(y + 6, 'lnight', T['lnight_table'])

    # note e fonti
    import textwrap
    ny = max(y + 6, H - 36)
    ax.add_patch(Rectangle((x0, ny - 6), x1 - x0, 0.3, color=RULE, lw=0))
    for k, line in enumerate(textwrap.wrap(T['note'], 118)):
        text(x0, ny + k * 4.2, line, 7.5, color=MID)
    text(x0, H - 12, T['sources'], 7, color=MID)
    text(x1, H - 12, f'Sonar · {model_name}', 7, 'bold', color=ACCENT, ha='right')
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
