"""HTTP con User-Agent identificabile, ripresa dei download e verifica dell'integrità."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .config import USER_AGENT

TIMEOUT = (20, 120)


class Cancelled(Exception):
    """Lavoro interrotto dall'utente."""


def session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    s.headers['User-Agent'] = USER_AGENT
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=('GET', 'HEAD'))
    s.mount('https://', HTTPAdapter(max_retries=retry))
    s.mount('http://', HTTPAdapter(max_retries=retry))
    return s


def get_json(url: str, params=None, timeout=TIMEOUT):
    with session() as s:
        response = s.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()


def get_text(url: str, timeout=TIMEOUT) -> str:
    with session() as s:
        response = s.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text


def file_md5(path: Path, chunk=8 * 1024 * 1024) -> str:
    digest = hashlib.md5()
    with open(path, 'rb') as stream:
        while block := stream.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def file_sha256(path: Path, chunk=8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path, progress=None, cancelled=None, expected_md5: str | None = None, max_bytes: int | None = None) -> Path:
    """Scarica in dest.part riprendendo da dove si era fermato; rinomina solo a download completo e verificato.

    progress(done_bytes, total_bytes) viene chiamata al massimo ogni mezzo secondo."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    with session() as s:
        head = s.head(url, allow_redirects=True, timeout=TIMEOUT)
        total = int(head.headers.get('Content-Length') or 0) or None
        if max_bytes and total and total > max_bytes:
            raise ValueError(f'File troppo grande ({total:,} byte): {url}')
        start = part.stat().st_size if part.exists() else 0
        if total and start > total:
            part.unlink(); start = 0
        headers = {'Range': f'bytes={start}-'} if start else {}
        with s.get(url, stream=True, headers=headers, timeout=TIMEOUT, allow_redirects=True) as response:
            if start and response.status_code != 206:
                start = 0  # il server ignora Range: si riparte da zero
            response.raise_for_status()
            mode = 'ab' if start else 'wb'
            done, last = start, 0.0
            with open(part, mode) as out:
                for block in response.iter_content(chunk_size=1024 * 1024):
                    if cancelled and cancelled():
                        raise Cancelled()
                    out.write(block)
                    done += len(block)
                    if max_bytes and done > max_bytes:
                        raise ValueError(f'Download oltre il limite di {max_bytes:,} byte: {url}')
                    now = time.monotonic()
                    if progress and now - last > 0.5:
                        progress(done, total); last = now
    if total and part.stat().st_size != total:
        raise IOError(f'Download incompleto: {part.stat().st_size:,} di {total:,} byte')
    if expected_md5 and file_md5(part) != expected_md5.lower():
        part.unlink()
        raise IOError(f'Checksum MD5 non corrispondente: {url}')
    part.replace(dest)
    if progress:
        progress(dest.stat().st_size, total)
    return dest


def human_bytes(value) -> str:
    if value is None:
        return '?'
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:,.0f} {unit}' if unit in ('B', 'KB') else f'{value:,.1f} {unit}'
        value /= 1024
