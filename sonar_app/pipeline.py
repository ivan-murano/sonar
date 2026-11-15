"""Lavoro completo per una città: cartella, download, modello, esportazione.

Gira nel processo worker (sonar_app.worker) e comunica con l'interfaccia tramite eventi:
  {"event": "progress", "value": 0..1, "stage": "...", "detail": "..."}
  {"event": "folder", "path": "..."}   {"event": "done", "path": "...", "seconds": ...}
  {"event": "error", "message": "..."}
"""
from __future__ import annotations

import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import __version__, export, providers
from .config import cache_dir, runs_dir
from .export import docs
from .i18n import filename, folder, pick, t
from .model_api import ModelContext, default_model, discover
from .places import City

# Peso delle fasi nella barra di avanzamento.
PHASES = {'prepare': (0.00, 0.02), 'download': (0.02, 0.35), 'model': (0.35, 0.90), 'export': (0.90, 1.00)}


class Reporter:
    def __init__(self, emit, language, log_path: Path | None = None):
        self.emit, self.language, self.log_file = emit, language, None
        self.stage, self.last = '', 0.0
        if log_path:
            self.open_log(log_path)

    def open_log(self, path: Path):
        self.log_file = open(path, 'a', encoding='utf-8')

    def log(self, text: str):
        line = f'{time.strftime("%H:%M:%S")} {text}'
        if self.log_file:
            self.log_file.write(line + '\n'); self.log_file.flush()
        self.emit({'event': 'log', 'text': str(text)})

    def phase(self, name: str, fraction: float, detail=''):
        lo, hi = PHASES[name]
        value = lo + (hi - lo) * max(0.0, min(1.0, fraction))
        self.last = max(self.last, value)  # la barra non torna mai indietro
        self.stage = t(f'stage_{name}', self.language)
        detail = pick(detail, self.language) if isinstance(detail, dict) else str(detail or '')
        self.emit({'event': 'progress', 'value': round(self.last, 4), 'stage': self.stage, 'detail': detail})

    def close(self):
        if self.log_file:
            self.log_file.close(); self.log_file = None


def run_job(spec: dict, emit, cancelled=lambda: False) -> Path:
    started = time.monotonic()
    language = spec.get('language', 'it')
    city = City.from_json(spec['city'])
    models = discover()
    model = next((m for m in models if m.id == spec.get('model_id')), None) or default_model()
    report = Reporter(emit, language)
    # 1. cartella e confine
    report.phase('prepare', 0.0)
    root = export.make_root(Path(spec['out_dir']), city.name)
    report.open_log(root / filename('log', language))
    emit({'event': 'folder', 'path': str(root)})
    report.log(f'Sonar {__version__} · {city.name} ({city.country_code}, LAU {city.gisco_id}) · {pick(model.manifest["name"], language)} {model.version} ({model.id})')
    inputs_root = root / folder('inputs', language)
    slug = export.safe_name(city.name)
    boundary = city.write_boundary(inputs_root / folder('boundary', language) / f'{slug}_{filename("boundary", language)}.gpkg')
    report.phase('prepare', 1.0)
    # 2. dati richiesti dal modello
    fetchers = providers.registry()
    inputs, sources = {}, {'boundary': {'dataset': f'Eurostat GISCO LAU {city.lau_year}', 'gisco_id': city.gisco_id, 'lau_id': city.lau_id,
                                        'license': 'non-commercial use, source acknowledgement', 'attribution': 'EuroGeographics',
                                        'path': str(boundary.relative_to(root))}}
    items = model.manifest['inputs']
    # i download sono indipendenti: si scaricano insieme (il più lungo, OSM con il ritaglio, non aspetta gli altri)
    progress = [0.0] * len(items)
    lock = threading.Lock()

    def fetch(i, item):
        provider = item['provider']

        def advance(f, msg, i=i):
            with lock:
                progress[i] = f
                report.phase('download', sum(progress) / len(items), msg)
        def log(text):
            with lock:
                report.log(text)
        job = providers.Job(language=language, cache=cache_dir(), log=log, cancelled=cancelled, report=advance)
        return fetchers[provider]({**item, '_slug': slug}, city, inputs_root / providers.FOLDER_NAMES[provider], job)

    if cancelled():
        raise SystemExit(3)
    with ThreadPoolExecutor(max_workers=max(1, len(items))) as pool:
        futures = [pool.submit(fetch, i, item) for i, item in enumerate(items)]
        results = [future.result() for future in futures]       # stesso ordine del manifest; un errore si propaga
    if cancelled():
        raise SystemExit(3)
    for item, result in zip(items, results):
        inputs[item['id']] = Path(result['path'])
        sources[item['id']] = {**result['source'], 'path': str(Path(result['path']).relative_to(root))}
        report.log(f'{item["provider"]}: {Path(result["path"]).name}')
    # 3. modello
    work = runs_dir() / root.name
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    (work / 'outputs').mkdir(parents=True)
    ctx = ModelContext(city=city.to_json() | {'geometry': None}, boundary=boundary, inputs=inputs, work_dir=work, output_dir=work / 'outputs',
                       language=language, model_dir=model.folder, progress=lambda f, msg=None: report.phase('model', f, msg or ''),
                       log=report.log, cancelled=cancelled)
    report.phase('model', 0.0, pick(model.manifest['name'], language))
    result = model.run(ctx)
    # 4. esportazione
    written = export.export_results(model, result['outputs'], root, city, boundary, language,
                                    lambda f, msg: report.phase('export', 0.9 * f, msg), report.log, inputs=inputs)
    report.phase('export', 0.95, t('ex_docs', language))
    export.write_sources(root, language, sources, city, model, {'model_metadata': result.get('metadata'), 'written': written,
                                                                'software_version': __version__})
    docs.write_documents(root, language, model, city)
    seconds = round(time.monotonic() - started, 1)
    report.log(f'OK {seconds} s')
    report.phase('export', 1.0, '')
    report.close()
    shutil.rmtree(work, ignore_errors=True)
    emit({'event': 'done', 'path': str(root), 'seconds': seconds, 'warnings': written.get('warnings', [])})
    return root


def run_job_safely(spec: dict, emit, cancelled=lambda: False) -> int:
    try:
        run_job(spec, emit, cancelled)
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        emit({'event': 'log', 'text': traceback.format_exc()})
        emit({'event': 'error', 'message': f'{type(exc).__name__}: {exc}'})
        return 1
