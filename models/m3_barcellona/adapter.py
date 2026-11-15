"""Adattatore del modello Pharos Noise (identificativo interno m3_barcellona) al contratto sonar-model/1.

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
    ('acquire', 0.00, 0.04, {'it': 'Controllo dei dati di input', 'en': 'Checking the input data'}),
    ('prepare', 0.04, 0.80, {'it': 'Preparazione della città', 'en': 'Preparing the city'}),
    ('predict', 0.80, 1.00, {'it': 'Calcolo dei livelli di rumore', 'en': 'Computing noise levels'}),
]
# Testi per la barra di avanzamento: i passi "k/6" di prepare e le fasi di predict, nella lingua scelta.
# Le righe del modello vanno solo nel registro; un passo non riconosciuto mostra «Passo k di n».
PREPARE_STEPS = {
    '1': {'it': 'Lettura di strade, edifici e punti di interesse (OpenStreetMap)', 'en': 'Reading roads, buildings and points of interest (OpenStreetMap)'},
    '1b': {'it': 'Conversione in coordinate metriche e attività (Overture)', 'en': 'Converting to metric coordinates and places (Overture)'},
    '2': {'it': 'Celle esagonali e segmenti stradali', 'en': 'Hexagonal cells and road segments'},
    '3': {'it': 'Punti di calcolo all’aperto', 'en': 'Outdoor calculation points'},
    '4': {'it': 'Contesto urbano entro 100, 250 e 500 m da ogni punto', 'en': 'Urban context within 100, 250 and 500 m of each point'},
    '5': {'it': 'Orari di apertura delle attività', 'en': 'Opening hours of businesses'},
    '6': {'it': 'Calendario e giorni di riferimento', 'en': 'Calendar and reference days'},
}
PREDICT_STEPS = [  # (inizio della riga del modello, testo)
    ('weekday', {'it': 'Previsione del giorno feriale', 'en': 'Weekday prediction'}),
    ('holiday', {'it': 'Previsione del giorno festivo', 'en': 'Holiday prediction'}),
    ('geopackage', {'it': 'Salvataggio dei risultati del modello', 'en': 'Saving the model results'}),
]


def code_root(model_dir: Path) -> Path:
    env = os.environ.get('SONAR_MODEL_CODE')
    for candidate in ([Path(env)] if env else []) + [model_dir / 'code']:
        if (candidate / 'src' / 'sonar' / 'cli.py').exists():
            return candidate.resolve()
    raise FileNotFoundError('Codice del modello Pharos Noise non trovato: impostare SONAR_MODEL_CODE oppure includere la cartella code/')


def _accelerate_static_features(code_paths=None):
    """Feature statiche con il calcolo accelerato di Sonar (stessi risultati, verificati dal modello a ogni esecuzione).

    Si sostituisce solo la funzione chiamata da `sonar.prepare.run_prepare`; il codice del modello non cambia.
    SONAR_FAST_FEATURES=0 ripristina il calcolo originale."""
    if os.environ.get('SONAR_FAST_FEATURES', '1') == '0':
        return
    import sonar.prepare as model_prepare
    from sonar_app.fastfeatures import compute_static_features

    def accelerated(receivers, roads, buildings, osm_static, places_static, cfg, cache_dir, workers=None, chunk=1000, log=print):
        if code_paths:   # matrici delle attività in anticipo (o tutto il calcolo anticipato, se non già avviato al passo 2)
            try:
                from sonar_app import speculative
                speculative.start(Path(cache_dir).parent, code_paths, receivers_ready=True)
            except Exception as exc:
                log(f'  calcolo anticipato non avviato ({type(exc).__name__}: {exc})')
        return compute_static_features(receivers, roads, buildings, osm_static, places_static, cfg, cache_dir, None, chunk, log)

    model_prepare.compute_static_features = accelerated


def _parallelize_model(code_paths, log):
    """Fasi a blocchi indipendenti (lettura OSM, ricevitori, matrici delle attività, previsione) su più processi.

    Ogni processo chiama la funzione originale del modello sul proprio blocco: risultati identici.
    Se una firma non è quella attesa (modello aggiornato), quella fase resta com'è. SONAR_PARALLEL=0 disattiva."""
    if os.environ.get('SONAR_PARALLEL', '1') == '0':
        return
    import functools
    import sonar.osm as model_osm
    import sonar.places as model_places
    import sonar.predict as model_predict
    import sonar.receivers as model_receivers
    import sonar.supports as model_supports
    from sonar.legacy import activity, engine
    from sonar_app import parallel, speculative
    city_prediction = engine()
    hours = activity()
    # profile_for: funzione pura (categoria -> profilo), chiamata una volta per attività: si memorizzano i risultati
    if not getattr(hours.profile_for, 'cache_info', None):
        hours.profile_for = functools.lru_cache(maxsize=None)(hours.profile_for)
    plan = [
        (model_osm, 'read_pbf', ['pbf_path', 'bounds', 'index_type', 'collect_road_ways', 'prefilter', 'log'],
         lambda f: parallel.parallel_read_pbf(f, 'sonar.osm', 'read_pbf', model_osm.KEYS, code_paths, log)),
        (model_supports, 'h3_cells', [], lambda f: speculative.start_before(f, code_paths)),
        (model_supports, 'road_segments', ['ways', 'boundary_metric', 'crs', 'max_length'],
         lambda f: speculative.start_before(parallel.parallel_road_segments(f, 'sonar.supports', 'road_segments', code_paths, log), code_paths)),
        (model_places, 'static_pois', ['places', 'osm', 'feature_cfg'], lambda f: speculative.wrap_static(f, log)),
        (model_receivers, 'select_receivers', ['units', 'buildings', 'boundary_metric', 'worldcover_path', 'crs', 'log', 'parts_dir', 'chunk'],
         lambda f: parallel.parallel_receivers(f, 'sonar.receivers', 'select_receivers', code_paths)),
        (model_places, 'activity_programs', ['places_in', 'osm_in', 'profiles', 'crs'],
         lambda f: speculative.wrap_programs(f, log)),
        (model_predict, 'program_matrices', ['points', 'places', 'programs', 'chunk'],
         lambda f: speculative.wrap_matrices(parallel.parallel_program_matrices(f, 'sonar.legacy', 'spatial_program_counts', code_paths, log), log)),
        (city_prediction, 'predict_scenarios', ['spatial', 'matrices', 'programs', 'models', 'calendar', 'scenarios', 'chunk_size', 'progress'],
         lambda f: parallel.parallel_predict(f, city_prediction.__name__, 'predict_scenarios', code_paths)),
    ]
    for module, name, expected, make in plan:
        function = getattr(module, name, None)
        if function is None or getattr(function, '_sonar_parallel', False):
            continue
        if not parallel.signature_matches(function, expected):
            log(f'Parallelizzazione di {name} non applicata: la funzione del modello è cambiata')
            continue
        wrapped = make(function); wrapped._sonar_parallel = True
        setattr(module, name, wrapped)


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
    code_paths = [str(code / 'scripts'), str(code / 'src')]
    _accelerate_static_features(code_paths)
    _parallelize_model(code_paths, ctx.log)

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
        step = re.match(r'^(\d+[a-z]?)/(\d+)\s', text)
        lowered = text.lower()
        if step:
            k, n = int(re.match(r'\d+', step.group(1)).group()), int(step.group(2))
            state['lo'], state['hi'] = (k - 1) / n, k / n
            state['inner'] = 0.0
            known = PREPARE_STEPS.get(step.group(1)) if name == 'prepare' and n == 6 else None
            state['step'] = known or {'it': f'Passo {k} di {n}', 'en': f'Step {k} of {n}'}
        elif name == 'predict' and any(lowered.startswith(key) for key, _ in PREDICT_STEPS):
            found = next(value for key, value in PREDICT_STEPS if lowered.startswith(key))
            if found is not state.get('step'):
                state['step'], state['inner'] = found, 0.0
        counter = None if step else re.search(r'([\d][\d,.]*)\s*/\s*([\d][\d,.]*)', text)
        if counter:
            done, total = (float(v.replace(',', '').replace('.', '')) for v in counter.groups())
            if total > 0:
                state['inner'] = max(state['inner'], min(1.0, done / total))
        elif not step:
            state['inner'] = min(0.9, state['inner'] + 0.05)
        within = state['lo'] + (state['hi'] - state['lo']) * state['inner']
        detail = state.get('step')
        if detail and counter and name in ('prepare', 'predict'):
            percent = int(100 * state['inner'])
            detail = {lang: f'{detail[lang]} · {percent}%' for lang in ('it', 'en')}
        ctx.progress(start + (end - start) * within, {lang: f'{label[lang]} · {detail[lang]}' if detail else label[lang] for lang in ('it', 'en')})

    def stage(index):
        state.update(stage=index, lo=0.0, hi=1.0, inner=0.0, step=None)
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
