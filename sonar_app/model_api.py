"""Contratto fra Sonar e i modelli acustici ("sonar-model/1").

Un modello è una cartella dentro models/ con:

    sonar_model.json   manifest: identità, dati richiesti, prodotti e stili (vedi docs/MODEL_CONTRACT.md)
    <modulo>.py        funzione indicata da "entrypoint" (es. "adapter:run")

Sonar scarica i dati elencati in "inputs", chiama run(ctx) e riceve i file prodotti; nomi,
cartelle, stili, formati (GPKG, File Geodatabase, PNG) e lingua sono compito del software.
Il modello non importa nulla da Qt e non scrive fuori da ctx.work_dir / ctx.output_dir.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import models_dir

CONTRACT = 'sonar-model/1'
KNOWN_PROVIDERS = ('osm_pbf', 'overture_places', 'esa_worldcover', 'ghsl_population')


class ModelError(Exception):
    """Manifest non valido o risultato del modello non conforme al contratto."""


@dataclass
class ModelContext:
    """Quello che Sonar passa a run(ctx)."""
    city: dict                      # name, country_code, lat, lon, lau_id, gisco_id, lau_name, lau_year, area_km2, population
    boundary: Path                  # GeoPackage EPSG:4326 con il confine LAU
    inputs: dict[str, Path]         # id dell'input nel manifest -> file scaricato
    work_dir: Path                  # cartella di lavoro del modello (temporanea)
    output_dir: Path                # dove il modello scrive i file dichiarati in "outputs"
    language: str                   # 'it' o 'en' (per i messaggi)
    model_dir: Path                 # cartella del pacchetto modello
    progress: Callable[[float, object], None] = field(default=lambda fraction, message=None: None)
    log: Callable[[str], None] = field(default=print)
    cancelled: Callable[[], bool] = field(default=lambda: False)


@dataclass
class Model:
    manifest: dict
    folder: Path

    @property
    def id(self) -> str:
        return self.manifest['id']

    @property
    def version(self) -> str:
        return str(self.manifest.get('version', '0'))

    def output(self, output_id: str) -> dict:
        for item in self.manifest['outputs']:
            if item['id'] == output_id:
                return item
        raise ModelError(f'Output non dichiarato nel manifest: {output_id}')

    def style(self, name: str) -> dict:
        try:
            return self.manifest['styles'][name]
        except KeyError as exc:
            raise ModelError(f'Stile non dichiarato nel manifest: {name}') from exc

    def entrypoint(self) -> Callable:
        module_name, _, function = self.manifest['entrypoint'].partition(':')
        path = self.folder / (module_name.replace('.', '/') + '.py')
        if not path.exists():
            raise ModelError(f'Entrypoint non trovato: {path}')
        name = f'sonar_model_{self.id}_{module_name.replace(".", "_")}'
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return getattr(module, function)

    def run(self, ctx: ModelContext) -> dict:
        result = self.entrypoint()(ctx)
        return validate_result(self, result, ctx.output_dir)


def validate_manifest(manifest: dict, folder: Path) -> dict:
    missing = [k for k in ('contract', 'id', 'version', 'name', 'entrypoint', 'inputs', 'outputs', 'styles') if k not in manifest]
    if missing:
        raise ModelError(f'{folder}: campi mancanti nel manifest: {missing}')
    if manifest['contract'] != CONTRACT:
        raise ModelError(f'{folder}: contratto {manifest["contract"]!r} non supportato (atteso {CONTRACT})')
    for item in manifest['inputs']:
        if item.get('provider') not in KNOWN_PROVIDERS:
            raise ModelError(f'{folder}: provider sconosciuto {item.get("provider")!r}; disponibili {KNOWN_PROVIDERS}')
    ids = [o['id'] for o in manifest['outputs']]
    if len(ids) != len(set(ids)):
        raise ModelError(f'{folder}: id di output duplicati')
    for output in manifest['outputs']:
        for key in ('id', 'file_stem', 'layers', 'style', 'map_fields'):
            if key not in output:
                raise ModelError(f'{folder}: output {output.get("id")} senza {key!r}')
        if output['style'] not in manifest['styles']:
            raise ModelError(f'{folder}: stile {output["style"]!r} non definito')
    for name, style in manifest['styles'].items():
        breaks, colors = style.get('breaks', []), style.get('colors', [])
        if len(colors) != len(breaks) + 1:
            raise ModelError(f'{folder}: lo stile {name} richiede len(colors) = len(breaks) + 1')
    return manifest


def validate_result(model: Model, result: dict, output_dir: Path) -> dict:
    """{'outputs': {output_id: path GPKG}, 'metadata': {...}}: ogni output dichiarato, file e layer presenti."""
    import pyogrio
    if not isinstance(result, dict) or 'outputs' not in result:
        raise ModelError("run(ctx) deve restituire un dict con la chiave 'outputs'")
    outputs = {}
    for output in model.manifest['outputs']:
        path = result['outputs'].get(output['id'])
        if path is None:
            if output.get('optional'):
                continue
            raise ModelError(f'Il modello non ha prodotto l’output {output["id"]}')
        path = Path(path)
        if not path.is_absolute():
            path = output_dir / path
        if not path.exists():
            raise ModelError(f'File di output mancante: {path}')
        layers = {name for name, _ in pyogrio.list_layers(path)}
        wanted = {layer['name'] for layer in output['layers']}
        if not wanted <= layers:
            raise ModelError(f'{path.name}: layer mancanti {sorted(wanted - layers)}')
        outputs[output['id']] = path
    return {'outputs': outputs, 'metadata': result.get('metadata') or {}}


def discover(folder: Path | None = None) -> list[Model]:
    folder = Path(folder or models_dir())
    models = []
    for manifest_path in sorted(folder.glob('*/sonar_model.json')):
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        models.append(Model(validate_manifest(manifest, manifest_path.parent), manifest_path.parent))
    return models


def default_model(folder: Path | None = None) -> Model:
    models = discover(folder)
    if not models:
        raise ModelError(f'Nessun modello in {folder or models_dir()}')
    preferred = [m for m in models if m.manifest.get('default')]
    return (preferred or models)[0]
