"""Processo di calcolo separato dall'interfaccia: legge il lavoro da un file JSON e scrive eventi su stdout.

    python -m sonar_app.worker lavoro.json      (da sorgente)
    Sonar.exe --worker lavoro.json              (eseguibile)

Ogni riga che inizia con SONAR_EVENT è un evento JSON per l'interfaccia; il resto è registro.
"""
from __future__ import annotations

import json
import os
import sys

EVENT_PREFIX = 'SONAR_EVENT '


def ensure_streams():
    """Nell'eseguibile senza console sys.stdout è None: lo collega alla pipe aperta dall'interfaccia."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    if os.name == 'nt':
        try:
            import ctypes
            import msvcrt
            kernel = ctypes.windll.kernel32
            kernel.GetStdHandle.restype = ctypes.c_void_p
            invalid = ctypes.c_void_p(-1).value
            for name, number in (('stdout', -11), ('stderr', -12)):
                if getattr(sys, name) is None:
                    handle = kernel.GetStdHandle(number)
                    if handle and handle != invalid:
                        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
                        setattr(sys, name, open(fd, 'w', encoding='utf-8', buffering=1, errors='replace'))
        except Exception:
            pass
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = sys.stdout


def emit(event: dict):
    print(EVENT_PREFIX + json.dumps(event, ensure_ascii=False, default=str), flush=True)


def main(argv: list[str]) -> int:
    ensure_streams()
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    except Exception:
        pass
    if not argv:
        print('uso: worker <lavoro.json>', file=sys.stderr)
        return 2
    spec = json.loads(open(argv[0], encoding='utf-8').read())
    from .pipeline import run_job_safely
    return run_job_safely(spec, emit)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
