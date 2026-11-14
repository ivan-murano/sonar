"""Adattatore del modello M3 al contratto sonar-model/1.

Chiama la pipeline del progetto del modello (pacchetto `sonar` in <codice>/src) con i dati già
scaricati da Sonar: acquire da file locali (nessun download), prepare, predict. Il codice del
modello si trova in, nell'ordine: $SONAR_MODEL_CODE, <cartella del modello>/code (incluso
nell'installazione). Questo file appartiene al modello: chi cambia il modello lo aggiorna.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Paesi: GISCO usa EL e UK, la libreria delle festività usa i codici ISO GR e GB.
ISO_FROM_GISCO = {'EL': 'GR', 'UK': 'GB'}
STAGES = [  # (prefisso dei messaggi del modello, inizio, fine, etichetta)
    ('acquire', 0.00, 0.04, {'it': 'Preparazione degli input', 'en': 'Preparing inputs'}),
    ('prepare', 0.04, 0.80, {'it': 'Supporti, ricevitori e variabili', 'en': 'Supports, receivers and features'}),
    ('predict', 0.80, 1.00, {'it': 'Previsioni ed esportazione', 'en': 'Predictions and export'}),
]


def code_root(model_dir: Path) -> Path:
    env = os.environ.get('SONAR_MODEL_CODE')
    for candidate in ([Path(env)] if env else []) + [model_dir / 'code']:
        if (candidate / 'src' / 'sonar' / 'cli.py').exists():
            return candidate.resolve()
    raise FileNotFoundError('Codice del modello M3 non trovato: impostare SONAR_MODEL_CODE oppure includere la cartella code/')


def run(ctx):
    code = code_root(ctx.model_dir)
    os.environ['SONAR_CODE'] = str(code)
    os.environ['SONAR_ROOT'] = str(ctx.work_dir)
    for folder in (code / 'scripts', code / 'src'):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    from sonar import cli
    from sonar.acquire import run_acquire
    from sonar.predict import run_predict
    from sonar.prepare import run_prepare
    from sonar.runs import city_slug

    city = ctx.city
    slug = city_slug(city.get('lau_name') or city['name'])
    country = ISO_FROM_GISCO.get(city['country_code'], city['country_code'])
    state = {'stage': 0, 'lo': 0.0, 'hi': 1.0, 'inner': 0.0}

    def log(text):
        text = str(text).strip()
        if not text:
            return
        ctx.log(text)
        name, start, end, label = STAGES[state['stage']]
        # passi "k/n Descrizione" del modello e contatori "x / y" dentro il passo
        step = re.match(r'^(\d+)[a-z]?/(\d+)\s', text)
        if step:
            k, n = int(step.group(1)), int(step.group(2))
            state['lo'], state['hi'] = (k - 1) / n, k / n
            state['inner'] = 0.0
        else:
            counter = re.search(r'([\d][\d,.]*)\s*/\s*([\d][\d,.]*)', text)
            if counter:
                done, total = (float(v.replace(',', '').replace('.', '')) for v in counter.groups())
                if total > 0:
                    state['inner'] = max(state['inner'], min(1.0, done / total))
            else:
                state['inner'] = min(0.9, state['inner'] + 0.05)
        within = state['lo'] + (state['hi'] - state['lo']) * state['inner']
        line = re.sub(r'\s+', ' ', text)[:140]
        ctx.progress(start + (end - start) * within, {'it': f'{label["it"]} · {line}', 'en': f'{label["en"]} · {line}'})

    def stage(index):
        state.update(stage=index, lo=0.0, hi=1.0, inner=0.0)
        _, start, _, label = STAGES[index]
        ctx.progress(start, label)

    parser = cli.parser()
    stage(0)
    args = parser.parse_args(['acquire', '--city', city['name'], '--city-id', slug, '--boundary', str(ctx.boundary), '--country', country,
                              '--osm-pbf', str(ctx.inputs['osm']), '--places', str(ctx.inputs['places']),
                              '--worldcover', str(ctx.inputs['landcover'])])
    acquired = run_acquire(args, log)
    stage(1)
    args = parser.parse_args(['prepare', '--city-id', slug, '--acquire-run', acquired['run_id']])
    prepared = run_prepare(args, log)
    stage(2)
    args = parser.parse_args(['predict', '--city-id', slug, '--prepare-run', prepared['run_id']])
    predicted = run_predict(args, log)
    folder = Path(os.environ['SONAR_ROOT']) / predicted['outputs_dir']
    ctx.progress(1.0, STAGES[2][3])
    return {'outputs': {'h3': folder / f'{slug}_rumore_h3.gpkg', 'strade': folder / f'{slug}_rumore_strade.gpkg'},
            'metadata': {'model_runs': {'acquire': acquired['run_id'], 'prepare': prepared['run_id'], 'predict': predicted['run_id']},
                         'exports': predicted.get('exports'), 'elapsed_seconds_predict': predicted.get('elapsed_seconds')}}
