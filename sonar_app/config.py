"""Percorsi, indirizzi e impostazioni del software (nessuna dipendenza da Qt o dal modello)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import APP_NAME, __version__

REPOSITORY_URL = 'https://github.com/ivan-murano/sonar'
USER_AGENT = f'{APP_NAME}/{__version__} (+{REPOSITORY_URL})'
CONTACT_EMAIL = None  # Nominatim chiede un recapito: l'URL del repository nell'User-Agent fa da riferimento


def frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def package_dir() -> Path:
    """Cartella del pacchetto sonar_app (dentro _internal nell'eseguibile)."""
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    """Radice dell'installazione: cartella dell'eseguibile, oppure radice del repository da sorgente."""
    if frozen():
        return Path(sys.executable).resolve().parent
    return package_dir().parent


def bundle_dir() -> Path:
    """Dove PyInstaller mette dati e moduli (sys._MEIPASS); da sorgente coincide con install_dir()."""
    return Path(getattr(sys, '_MEIPASS', install_dir()))


def assets_dir() -> Path:
    return package_dir() / 'assets'


def models_dir() -> Path:
    """Pacchetti modello: SONAR_MODELS_DIR, poi models/ accanto all'eseguibile o nel repository."""
    if os.environ.get('SONAR_MODELS_DIR'):
        return Path(os.environ['SONAR_MODELS_DIR']).resolve()
    for base in (bundle_dir(), install_dir()):
        if (base / 'models').is_dir():
            return base / 'models'
    return install_dir() / 'models'


def user_data_dir() -> Path:
    """Impostazioni e cache dell'utente (%LOCALAPPDATA%\\Sonar su Windows)."""
    if os.environ.get('SONAR_HOME'):
        return Path(os.environ['SONAR_HOME']).resolve()
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / APP_NAME
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / APP_NAME.lower()


def cache_dir() -> Path:
    """Download riutilizzabili fra città (estratti OSM regionali, confini, tile)."""
    path = user_data_dir() / 'cache'
    path.mkdir(parents=True, exist_ok=True)
    return path


def runs_dir() -> Path:
    """Cartelle di lavoro temporanee del modello."""
    path = user_data_dir() / 'runs'
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return user_data_dir() / 'settings.json'


def load_settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_settings(values: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_settings()
    current.update(values)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
