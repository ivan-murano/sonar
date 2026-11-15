"""Popolazione esposta: residenti per classe di Lden e Lnight, tabelle A4 (PNG) e foglio di calcolo (XLSX).

I residenti GHS-POP (griglia 100 m) sono attribuiti alle celle H3 con ponderazione areale (densità uniforme in ogni
pixel), limitata al confine comunale. Classi della Direttiva 2002/49/CE, allegato VI (Lden 55-59 ... >= 75,
Lnight 50-54 ... >= 70) e soglie delle linee guida OMS 2018 per il traffico stradale (Lden 53 dB, Lnight 45 dB).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

LDEN_EDGES = [55, 60, 65, 70, 75]
LNIGHT_EDGES = [50, 55, 60, 65, 70]
THRESHOLDS = [('lden', 53, 'who'), ('lnight', 45, 'who'), ('lden', 55, 'end'), ('lnight', 50, 'end'), ('lden', 65, 'high'), ('lnight', 55, 'high')]
FIELDS = {'lden': 'lden_ind', 'lnight': 'lnight_ind'}
RES_FIELD = 'residenti'

TXT = {
    'it': {'title': '{city} — popolazione esposta al rumore', 'subtitle': 'Residenti per classe di Lden e Lnight · {model} · popolazione GHS-POP 2020',
           'total': 'Residenti', 'who_lden': 'Lden ≥ 53 dB', 'who_lnight': 'Lnight ≥ 45 dB', 'who': 'soglie OMS 2018',
           'end_lden': 'Lden ≥ 55 dB', 'end_lnight': 'Lnight ≥ 50 dB', 'end': 'soglie di mappatura della Direttiva 2002/49/CE',
           'high_lden': 'Lden ≥ 65 dB', 'high_lnight': 'Lnight ≥ 55 dB', 'high': 'esposizione elevata',
           'class': 'Classe (dB)', 'residents': 'Residenti', 'share': 'Quota', 'none': 'senza stima', 'below': '< {v}',
           'total_row': 'Totale', 'lden_table': 'Lden — giorno, sera, notte', 'lnight_table': 'Lnight — notte 23–07',
           'note': ('Lden e Lnight calcolati da Sonar sommando l’energia sonora delle sei fasce orarie del modello (sera +5 dB, notte +10 dB). '
                    'Residenti GHS-POP R2023A 2020 attribuiti alle celle H3 di circa 100 m per area, entro il confine comunale. '
                    'Classi della Direttiva 2002/49/CE (allegato VI); soglie OMS 2018 per il traffico stradale.'),
           'sources': 'Fonti: OpenStreetMap, Overture Maps, ESA WorldCover, JRC GHSL (Schiavina et al. 2023), confini © EuroGeographics',
           'sheet_summary': 'Sintesi', 'sheet_cells': 'Celle H3', 'sheet_notes': 'Note', 'indicator': 'Indicatore', 'threshold': 'Soglia',
           'reference': 'Riferimento', 'cell_id': 'Cella H3', 'city_label': 'Città', 'model_label': 'Modello', 'pop_label': 'Popolazione',
           'tile_modal': 'Lden più frequente', 'tile_caption': 'Quote sul totale dei residenti · classi della Direttiva 2002/49/CE, allegato VI',
           'read_title': 'Un modello verificato sulle misure',
           'validity': ('Il modello stima il livello sonoro ogni 100 m: su 30 postazioni di Barcellona mai usate per l’addestramento '
                        'l’errore medio è di 3,6 dB sulle singole ore, con una correlazione di 0,88 con le misure. Tavola, foglio di calcolo '
                        'e layer GIS mostrano quanti residenti vivono in ogni classe di esposizione e dove: la base per decidere dove misurare, '
                        'dove intervenire per primi e quali scenari confrontare.'),
           'validity_generic': ('Livelli sonori stimati dal modello «{model}» su celle di circa 100 m. Tavola, foglio di calcolo e layer GIS mostrano '
                                'quanti residenti vivono in ogni classe di esposizione e dove: la base per decidere dove misurare, dove intervenire '
                                'per primi e quali scenari confrontare.'),
           'of_residents': 'dei residenti',
           'total_label': 'Residenti nel comune', 'unit': 'residenti'},
    'en': {'title': '{city} — population exposed to noise', 'subtitle': 'Residents by Lden and Lnight class · {model} · GHS-POP 2020 population',
           'total': 'Residents', 'who_lden': 'Lden ≥ 53 dB', 'who_lnight': 'Lnight ≥ 45 dB', 'who': 'WHO 2018 thresholds',
           'end_lden': 'Lden ≥ 55 dB', 'end_lnight': 'Lnight ≥ 50 dB', 'end': 'Directive 2002/49/EC mapping thresholds',
           'high_lden': 'Lden ≥ 65 dB', 'high_lnight': 'Lnight ≥ 55 dB', 'high': 'high exposure',
           'class': 'Class (dB)', 'residents': 'Residents', 'share': 'Share', 'none': 'no estimate', 'below': '< {v}',
           'total_row': 'Total', 'lden_table': 'Lden — day, evening, night', 'lnight_table': 'Lnight — night 23–07',
           'note': ('Lden and Lnight computed by Sonar by summing the sound energy of the model’s six time bands (evening +5 dB, night +10 dB). '
                    'GHS-POP R2023A 2020 residents assigned to ~100 m H3 cells by area, within the municipal boundary. '
                    'Classes of Directive 2002/49/EC (Annex VI); WHO 2018 road traffic thresholds.'),
           'sources': 'Sources: OpenStreetMap, Overture Maps, ESA WorldCover, JRC GHSL (Schiavina et al. 2023), boundaries © EuroGeographics',
           'sheet_summary': 'Summary', 'sheet_cells': 'H3 cells', 'sheet_notes': 'Notes', 'indicator': 'Indicator', 'threshold': 'Threshold',
           'reference': 'Reference', 'cell_id': 'H3 cell', 'city_label': 'City', 'model_label': 'Model', 'pop_label': 'Population',
           'tile_modal': 'Most common Lden', 'tile_caption': 'Shares of all residents · classes of Directive 2002/49/EC, Annex VI',
           'read_title': 'A model checked against measurements',
           'validity': ('The model estimates the sound level every 100 m: at 30 Barcelona stations never used in training its mean error '
                        'is 3.6 dB on individual hours, with a correlation of 0.88 with the measurements. The sheet, the spreadsheet and the '
                        'GIS layers show how many residents live in each exposure class and where: the basis for deciding where to measure, '
                        'where to act first and which scenarios to compare.'),
           'validity_generic': ('Sound levels estimated by the model “{model}” on cells of about 100 m. The sheet, the spreadsheet and the GIS layers '
                                'show how many residents live in each exposure class and where: the basis for deciding where to measure, where '
                                'to act first and which scenarios to compare.'),
           'of_residents': 'of residents',
           'total_label': 'Residents in the municipality', 'unit': 'residents'},
}


def residents_per_cell(frame, raster_path: Path, boundary) -> np.ndarray:
    """Residenti di ogni poligono di `frame` (celle H3) dalla griglia GHS-POP, entro il confine."""
    import geopandas as gpd
    import rasterio
    import shapely
    with rasterio.open(raster_path) as src:
        data = src.read(1).astype('float64')
        nodata, transform, crs = src.nodata, src.transform, src.crs
    mask = data > 0
    if nodata is not None:
        mask &= data != nodata
    rows, cols = np.nonzero(mask)
    xs0, ys0 = transform * (cols, rows)
    xs1, ys1 = transform * (cols + 1, rows + 1)
    pixels = gpd.GeoSeries(shapely.box(xs0, ys1, xs1, ys0), crs=crs).to_crs(frame.crs)
    values = data[rows, cols]
    border = shapely.union_all(boundary.to_crs(frame.crs).geometry.to_numpy())
    targets = shapely.intersection(frame.geometry.to_numpy(), border)
    pgeom = pixels.to_numpy()
    parea = shapely.area(pgeom)
    tree = shapely.STRtree(pgeom)
    t_idx, s_idx = tree.query(targets, predicate='intersects')
    covered = shapely.covered_by(pgeom[s_idx], targets[t_idx])
    fraction = np.ones(len(s_idx))
    partial = ~covered
    if partial.any():
        fraction[partial] = shapely.area(shapely.intersection(pgeom[s_idx[partial]], targets[t_idx[partial]])) / parea[s_idx[partial]]
    return np.bincount(t_idx, weights=values[s_idx] * fraction, minlength=len(frame))


def class_rows(values, residents, edges):
    """[(etichetta, residenti)] dalla classe più bassa alla più alta, più 'senza stima'."""
    values = np.asarray(values, dtype=float)
    labels = [('below', edges[0])] + [f'{a}–{b - 1}' for a, b in zip(edges[:-1], edges[1:])] + [f'≥ {edges[-1]}']
    known = ~np.isnan(values)
    idx = np.digitize(values[known], edges)
    sums = np.bincount(idx, weights=residents[known], minlength=len(edges) + 1)
    rows = [(label, float(s)) for label, s in zip(labels, sums)]
    rows.append((('none', None), float(residents[~known].sum())))
    return rows


def compute(days, raster_path: Path, boundary) -> dict:
    """days: [(titolo del giorno, nome breve, frame con lden_ind/lnight_ind)] sulle stesse celle. Restituisce le tabelle."""
    import pandas as pd
    first = days[0][2]
    residents = residents_per_cell(first, raster_path, boundary)
    by_id = pd.Series(residents, index=first['unit_id'].astype(str).to_numpy()) if 'unit_id' in first else None
    unit_ids = first['unit_id'].astype(str).to_numpy() if 'unit_id' in first else np.arange(len(first)).astype(str)
    out = {'total': float(residents.sum()), 'days': [], 'residents': residents, 'residents_by_day': [], 'unit_ids': unit_ids}
    for title, short, frame in days:
        if by_id is not None and 'unit_id' in frame:
            res = by_id.reindex(frame['unit_id'].astype(str).to_numpy()).fillna(0.0).to_numpy()
            aligned = frame.set_index(frame['unit_id'].astype(str)).reindex(by_id.index)
        else:
            res, aligned = residents, frame
        out['residents_by_day'].append(np.round(res, 3))   # 0,1 per cella perdeva ~10 residenti a Melfi
        day = {'title': title, 'short': short, 'frame': aligned}
        for key, edges in (('lden', LDEN_EDGES), ('lnight', LNIGHT_EDGES)):
            day[key] = class_rows(frame[FIELDS[key]].to_numpy(), res, edges)
        day['thresholds'] = [(key, value, kind, float(res[np.nan_to_num(frame[FIELDS[key]].to_numpy(dtype=float), nan=-1e9) >= value].sum()))
                             for key, value, kind in THRESHOLDS]
        out['days'].append(day)
    return out


def _label(label, language):
    T = TXT[language]
    if isinstance(label, tuple):
        kind, value = label
        return T['below'].format(v=value) if kind == 'below' else T['none']
    return label


def _fmt(n, language):
    s = f'{int(round(n)):,}'
    return s.replace(',', '.') if language == 'it' else s


def _pct(n, total, language):
    if not total:
        return '–'
    s = '< 0.1%' if 0 < 100 * n / total < 0.05 else f'{100 * n / total:.1f}%'
    return s.replace('.', ',') if language == 'it' else s


# ---------------------------------------------------------------- foglio di calcolo

def write_xlsx(path: Path, result: dict, city: str, model_name: str, language: str) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    T = TXT[language]
    wb = Workbook()
    font, bold, head = Font(name='Arial', size=10), Font(name='Arial', size=10, bold=True), Font(name='Arial', size=10, bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='1F4E79')
    thin = Border(bottom=Side(style='thin', color='BFBFBF'))
    pct, num = '0.0%', '#,##0'

    def header(ws, row, values):
        for c, v in enumerate(values, 1):
            cell = ws.cell(row, c, v); cell.font = head; cell.fill = fill; cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    ws = wb.active; ws.title = T['sheet_summary']
    ws['A1'] = T['title'].format(city=city); ws['A1'].font = Font(name='Arial', size=14, bold=True)
    ws['A2'] = T['subtitle'].format(model=model_name); ws['A2'].font = Font(name='Arial', size=10, italic=True)
    ws['A4'] = T['total_label']; ws['A4'].font = bold
    ws['B4'] = round(result['total']); ws['B4'].number_format = num; ws['B4'].font = bold
    days = result['days']
    cols = [T['indicator'], T['reference']]
    for d in days:
        cols += [f'{d["short"]} · {T["residents"]}', f'{d["short"]} · {T["share"]}']
    header(ws, 6, cols)
    for r, (key, value, kind) in enumerate(THRESHOLDS, 7):
        ws.cell(r, 1, T[f'{kind}_{key}']).font = font
        ws.cell(r, 2, T[kind]).font = font
        for i, d in enumerate(days):
            c = 3 + 2 * i
            cell = ws.cell(r, c, round(d['thresholds'][r - 7][3])); cell.number_format = num; cell.font = font
            share = ws.cell(r, c + 1, f'=IF($B$4>0,{get_column_letter(c)}{r}/$B$4,0)'); share.number_format = pct; share.font = font
        for c in range(1, len(cols) + 1):
            ws.cell(r, c).border = thin
    row = 7 + len(THRESHOLDS) + 1
    for key, title in (('lden', T['lden_table']), ('lnight', T['lnight_table'])):
        ws.cell(row, 1, title).font = Font(name='Arial', size=12, bold=True)
        row += 1
        header(ws, row, [T['class'], ''] + sum([[f'{d["short"]} · {T["residents"]}', f'{d["short"]} · {T["share"]}'] for d in days], []))
        first = row + 1
        n = len(days[0][key])
        for j in range(n):
            r = first + j
            ws.cell(r, 1, _label(days[0][key][j][0], language)).font = font
            for i, d in enumerate(days):
                c = 3 + 2 * i
                cell = ws.cell(r, c, round(d[key][j][1])); cell.number_format = num; cell.font = font
                share = ws.cell(r, c + 1, f'=IF($B$4>0,{get_column_letter(c)}{r}/$B$4,0)'); share.number_format = pct; share.font = font
            for c in range(1, len(cols) + 1):
                ws.cell(r, c).border = thin
        r = first + n
        ws.cell(r, 1, T['total_row']).font = bold
        for i in range(len(days)):
            c = 3 + 2 * i
            L = get_column_letter(c)
            cell = ws.cell(r, c, f'=SUM({L}{first}:{L}{r - 1})'); cell.number_format = num; cell.font = bold
            share = ws.cell(r, c + 1, f'=IF($B$4>0,{L}{r}/$B$4,0)'); share.number_format = pct; share.font = bold
        row = r + 2
    ws.column_dimensions['A'].width = 34; ws.column_dimensions['B'].width = 40
    for c in range(3, len(cols) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 18
    ws.freeze_panes = 'A7'

    # per cella
    wc = wb.create_sheet(T['sheet_cells'])
    names = [T['cell_id'], T['residents']] + sum([[f'Lden · {d["short"]}', f'Lnight · {d["short"]}'] for d in days], [])
    header(wc, 1, names)
    unit_ids = result.get('unit_ids')
    if unit_ids is None:
        unit_ids = np.arange(len(result['residents'])).astype(str)
    columns = [days[i]['frame'][FIELDS[k]].to_numpy(dtype=float) for i in range(len(days)) for k in ('lden', 'lnight')]
    for i, uid in enumerate(unit_ids):
        values = [uid, round(float(result['residents'][i]), 2)] + [None if math.isnan(col[i]) else round(float(col[i]), 1) for col in columns]
        wc.append(values)
    for c in range(1, len(names) + 1):
        wc.column_dimensions[get_column_letter(c)].width = 20 if c == 1 else 16
    wc.freeze_panes = 'A2'
    wc.auto_filter.ref = f'A1:{get_column_letter(len(names))}{len(unit_ids) + 1}'

    wn = wb.create_sheet(T['sheet_notes'])
    for i, line in enumerate([T['note'], T['sources']], 1):
        wn.cell(i, 1, line).font = font
        wn.cell(i, 1).alignment = Alignment(wrap_text=True, vertical='top')
    wn.column_dimensions['A'].width = 120
    for row_cells in wc.iter_rows(min_row=2):
        for cell in row_cells:
            cell.font = font
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    return path


# ---------------------------------------------------------------- tavola A4

def render_png(path: Path, result: dict, city: str, model_name: str, language: str, model_id: str | None = None) -> Path:
    from .exposure_sheet import render
    return render(path, result, city, model_name, language, model_id=model_id)
