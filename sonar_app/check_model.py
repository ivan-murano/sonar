"""Verifica dei pacchetti modello: python -m sonar_app.check_model [cartella_models]"""
from __future__ import annotations

import sys
from pathlib import Path

from .i18n import pick
from .model_api import ModelError, discover


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    folder = Path(argv[0]) if argv else None
    try:
        models = discover(folder)
    except ModelError as exc:
        print(f'ERRORE: {exc}')
        return 1
    if not models:
        print('Nessun modello trovato')
        return 1
    for model in models:
        m = model.manifest
        print(f'{model.id} {model.version}{"  (predefinito)" if m.get("default") else ""}: {pick(m["name"], "it")}')
        print(f'  entrypoint {m["entrypoint"]}, documentazione {m.get("documentation_url")}')
        print(f'  input: {", ".join(i["id"] + "=" + i["provider"] for i in m["inputs"])}')
        for output in m['outputs']:
            print(f'  output {output["id"]}: layer {[layer["name"] for layer in output["layers"]]}, stile {output["style"]}, '
                  f'{len(output["map_fields"])} campi in mappa')
        try:
            model.entrypoint()
            print('  entrypoint importabile: sì')
        except Exception as exc:
            print(f'  entrypoint importabile: NO ({exc})')
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
