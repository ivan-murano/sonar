"""Raccoglie i testi di licenza dei pacchetti Python installati in <dist>/licenses/<pacchetto>/."""
import importlib.metadata as md
import shutil
import sys
from pathlib import Path


def main(argv):
    target = Path(argv[0]) / 'licenses'
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for dist in md.distributions():
        name = dist.metadata['Name']
        files = [f for f in (dist.files or []) if any(k in f.name.upper() for k in ('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'AUTHORS'))
                 or 'licenses' in [p.lower() for p in f.parts]]
        for f in files:
            src = Path(dist.locate_file(f))
            if src.is_file():
                dest = target / f'{name}-{dist.version}' / f.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                count += 1
    print(f'{count} file di licenza copiati in {target}')


if __name__ == '__main__':
    main(sys.argv[1:])
