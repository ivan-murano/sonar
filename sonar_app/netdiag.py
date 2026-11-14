"""Diagnosi della connessione HTTPS passo per passo: Sonar.exe --netdiag (scrive netdiag.txt accanto all'eseguibile)."""
from __future__ import annotations

import os
import sys
import traceback


def run(host: str = 'gisco-services.ec.europa.eu') -> int:
    from . import config
    lines = [f'python {sys.version}', f'frozen {config.frozen()}', f'executable {sys.executable}']
    lines += [f'ENV {k}={v}' for k, v in sorted(os.environ.items())
              if any(s in k.upper() for s in ('SSL', 'CERT', 'CA_BUNDLE', 'PROXY', 'OPENSSL', 'CURL', 'REQUESTS', 'PYTHON'))]

    def step(label, function):
        try:
            lines.append(f'OK   {label}: {function()}')
            return True
        except BaseException:
            lines.append(f'ERR  {label}:\n{traceback.format_exc()}')
            return False

    import socket
    import ssl
    from . import net
    bundle = net.ca_bundle()
    step('ca_bundle', lambda: f'{bundle} exists={os.path.exists(bundle) if isinstance(bundle, str) else bundle}')
    step('ssl', lambda: f'{ssl.OPENSSL_VERSION} {ssl.get_default_verify_paths()}')
    step('getaddrinfo', lambda: socket.getaddrinfo(host, 443)[0][4])

    def raw_tls():
        context = ssl.create_default_context(cafile=bundle if isinstance(bundle, str) else None)
        with socket.create_connection((host, 443), timeout=20) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                return tls.version()
    step('TLS con ssl', raw_tls)

    def urllib3_context():
        from urllib3.util.ssl_ import create_urllib3_context
        context = create_urllib3_context()
        context.load_verify_locations(bundle if isinstance(bundle, str) else None)
        return 'ok'
    step('contesto urllib3', urllib3_context)

    def urllib3_get():
        import urllib3
        pool = urllib3.PoolManager(ca_certs=bundle if isinstance(bundle, str) else None, retries=False)
        return pool.request('GET', f'https://{host}/', timeout=20).status
    step('GET urllib3', urllib3_get)

    def requests_get():
        import requests
        return requests.get(f'https://{host}/', timeout=20, verify=bundle).status_code
    step('GET requests', requests_get)

    def requests_get_no_env():
        import requests
        s = requests.Session()
        s.trust_env = False
        return s.get(f'https://{host}/', timeout=20, verify=bundle).status_code
    step('GET requests senza proxy di sistema', requests_get_no_env)

    def proxies():
        import urllib.request
        return urllib.request.getproxies()
    step('proxy di sistema', proxies)
    text = '\n'.join(lines)
    print(text, flush=True)
    try:
        (config.install_dir() / 'netdiag.txt').write_text(text, encoding='utf-8')
    except OSError:
        pass
    return 0
