"""Copia i pacchetti modello in dist/Sonar/models e, per ciascuno, il codice del modello indicato da code.bundle.

    python build/bundle_models.py <cartella_dist_Sonar> [radice_codice_modello]

La radice del codice viene da: argomento, variabile indicata in code.env (es. SONAR_MODEL_CODE).
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv):
    dist = Path(argv[0])
    explicit = Path(argv[1]) if len(argv) > 1 else None
    for manifest_path in sorted((ROOT / 'models').glob('*/sonar_model.json')):
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        source = manifest_path.parent
        target = dist / 'models' / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'code'))
        code = manifest.get('code') or {}
        if not code:
            continue
        root = explicit or (Path(os.environ[code['env']]) if code.get('env') and os.environ.get(code['env']) else None)
        if root is None or not root.is_dir():
            raise SystemExit(f'{manifest["id"]}: radice del codice del modello non trovata (impostare {code.get("env")})')
        files = sorted({p for pattern in code.get('bundle', []) for p in root.glob(pattern) if p.is_file() and '__pycache__' not in p.parts})
        if not files:
            raise SystemExit(f'{manifest["id"]}: nessun file corrisponde a code.bundle in {root}')
        for path in files:
            dest = target / code.get('bundled_dir', 'code') / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        print(f'{manifest["id"]}: {len(files)} file del modello copiati da {root}')


if __name__ == '__main__':
    main(sys.argv[1:])
