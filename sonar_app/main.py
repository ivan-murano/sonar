"""Punto di ingresso: interfaccia, oppure processo di calcolo con --worker."""
from __future__ import annotations

import multiprocessing
import sys


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    argv = list(sys.argv if argv is None else argv)
    if len(argv) > 1 and argv[1] == '--worker':
        from .worker import main as worker_main
        return worker_main(argv[2:])
    if len(argv) > 1 and argv[1] == '--selftest':
        from .worker import ensure_streams
        ensure_streams()
        from .selftest import run as selftest
        return selftest()
    if len(argv) > 1 and argv[1] == '--netdiag':
        from .worker import ensure_streams
        ensure_streams()
        from .netdiag import run as netdiag
        return netdiag()
    if len(argv) > 1 and argv[1] in ('--version', '-V'):
        from . import __version__
        print(f'Sonar {__version__}')
        return 0
    from .ui.app import run
    return run(argv)


if __name__ == '__main__':
    raise SystemExit(main())
