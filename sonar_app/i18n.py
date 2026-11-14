"""Testi dell'interfaccia e nomi delle cartelle di consegna in italiano e inglese."""
from __future__ import annotations

LANGUAGES = ('it', 'en')
DEFAULT_LANGUAGE = 'it'

STRINGS = {
    # interfaccia
    'subtitle': {'it': 'CALCOLATORE DI INQUINAMENTO ACUSTICO IN CITTÀ', 'en': 'URBAN NOISE POLLUTION CALCULATOR'},
    'placeholder': {'it': 'Inserisci città', 'en': 'Enter city'},
    'start': {'it': 'Avvia', 'en': 'Start'},
    'cancel': {'it': 'Annulla', 'en': 'Cancel'},
    'open_folder': {'it': 'Apri cartella', 'en': 'Open folder'},
    'open_log': {'it': 'Apri registro', 'en': 'Open log'},
    'minimize': {'it': 'Riduci a icona', 'en': 'Minimize'},
    'close': {'it': 'Chiudi', 'en': 'Close'},
    'theme_tip': {'it': 'Tema chiaro / scuro', 'en': 'Light / dark theme'},
    'language_tip': {'it': 'Lingua', 'en': 'Language'},
    'searching': {'it': 'Cerco la città…', 'en': 'Looking up the city…'},
    'boundary_loading': {'it': 'Recupero i confini amministrativi…', 'en': 'Fetching the administrative boundary…'},
    'city_found': {'it': '{name} · {country} · {area} km²', 'en': '{name} · {country} · {area} km²'},
    'city_hint': {'it': 'Confine LAU {lau} (Eurostat GISCO {year})', 'en': 'LAU boundary {lau} (Eurostat GISCO {year})'},
    'not_found': {'it': 'Nessuna città trovata con questo nome.', 'en': 'No city found with this name.'},
    'not_europe': {'it': 'Sonar copre le città europee con confini Eurostat (LAU).', 'en': 'Sonar covers European cities with Eurostat (LAU) boundaries.'},
    'type_city': {'it': 'Scrivi il nome di una città.', 'en': 'Type the name of a city.'},
    'network_error': {'it': 'Servizio non raggiungibile. Controlla la connessione.', 'en': 'Service unreachable. Check your connection.'},
    'choose_city_title': {'it': 'Quale città?', 'en': 'Which city?'},
    'choose_city_text': {'it': 'Il nome indica più luoghi: scegli quello giusto.', 'en': 'The name matches several places: pick the right one.'},
    'use': {'it': 'Usa', 'en': 'Use'},
    'choose_folder': {'it': 'Dove salvo dati e risultati?', 'en': 'Where should data and results be saved?'},
    'starting': {'it': 'Avvio…', 'en': 'Starting…'},
    'done': {'it': 'Fatto. Risultati e dati di input salvati.', 'en': 'Done. Results and input data saved.'},
    'failed': {'it': 'Elaborazione non riuscita.', 'en': 'Processing failed.'},
    'cancelled': {'it': 'Interrotto. I download completati restano in cache.', 'en': 'Stopped. Completed downloads stay in the cache.'},
    'confirm_stop_title': {'it': 'Interrompere?', 'en': 'Stop?'},
    'confirm_stop_text': {'it': "L'elaborazione in corso verrà fermata.", 'en': 'The running job will be stopped.'},
    'confirm_close_title': {'it': 'Chiudere Sonar?', 'en': 'Close Sonar?'},
    'confirm_close_text': {'it': "C'è un'elaborazione in corso: chiudendo verrà interrotta.", 'en': 'A job is running: closing will stop it.'},
    'stop': {'it': 'Interrompi', 'en': 'Stop'},
    'continue': {'it': 'Continua', 'en': 'Continue'},
    'no_model': {'it': 'Nessun modello installato.', 'en': 'No model installed.'},
    # fasi del lavoro
    'stage_prepare': {'it': 'Preparo la cartella', 'en': 'Preparing the folder'},
    'stage_download': {'it': 'Scarico i dati', 'en': 'Downloading data'},
    'stage_model': {'it': 'Calcolo il modello', 'en': 'Running the model'},
    'stage_export': {'it': 'Esporto i risultati', 'en': 'Exporting results'},
    'dl_osm_index': {'it': 'OpenStreetMap: scelgo l’estratto Geofabrik', 'en': 'OpenStreetMap: choosing the Geofabrik extract'},
    'dl_osm': {'it': 'OpenStreetMap: {name} ({done} / {total})', 'en': 'OpenStreetMap: {name} ({done} / {total})'},
    'dl_osm_cached': {'it': 'OpenStreetMap: estratto {name} già in cache', 'en': 'OpenStreetMap: extract {name} already cached'},
    'dl_osm_clip': {'it': 'OpenStreetMap: ritaglio l’area della città', 'en': 'OpenStreetMap: clipping the city area'},
    'dl_places': {'it': 'Overture Places: attività nel riquadro ({rows} righe)', 'en': 'Overture Places: activities in the area ({rows} rows)'},
    'dl_worldcover': {'it': 'ESA WorldCover: copertura del suolo', 'en': 'ESA WorldCover: land cover'},
    'ex_gpkg': {'it': 'GeoPackage con stile: {name}', 'en': 'Styled GeoPackage: {name}'},
    'ex_gdb': {'it': 'File Geodatabase ESRI', 'en': 'ESRI File Geodatabase'},
    'ex_png': {'it': 'Mappa PNG: {name}', 'en': 'PNG map: {name}'},
    'ex_docs': {'it': 'Licenza, autori e istruzioni', 'en': 'License, authors and instructions'},
}

# Nomi delle cartelle e dei file di consegna.
FOLDERS = {
    'results': {'it': 'Risultati', 'en': 'Results'},
    'gpkg': {'it': 'GeoPackage', 'en': 'GeoPackage'},
    'gdb': {'it': 'File Geodatabase', 'en': 'File Geodatabase'},
    'maps': {'it': 'Mappe', 'en': 'Maps'},
    'inputs': {'it': 'Dati di input', 'en': 'Input data'},
    'boundary': {'it': 'Confine', 'en': 'Boundary'},
    'arcgis_styles': {'it': 'Stili ArcGIS', 'en': 'ArcGIS styles'},
}
FILES = {
    'readme': {'it': 'LEGGIMI.txt', 'en': 'README.txt'},
    'license': {'it': 'LICENZA.txt', 'en': 'LICENSE.txt'},
    'authors': {'it': 'AUTORI.txt', 'en': 'AUTHORS.txt'},
    'sources': {'it': 'fonti_dati.json', 'en': 'data_sources.json'},
    'log': {'it': 'registro.txt', 'en': 'log.txt'},
    'boundary': {'it': 'confine', 'en': 'boundary'},
}


def t(key: str, lang: str, **values) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry[DEFAULT_LANGUAGE]
    return text.format(**values) if values else text


def folder(key: str, lang: str) -> str:
    return FOLDERS[key].get(lang) or FOLDERS[key][DEFAULT_LANGUAGE]


def filename(key: str, lang: str) -> str:
    return FILES[key].get(lang) or FILES[key][DEFAULT_LANGUAGE]


def pick(value, lang: str) -> str:
    """Testo localizzato da un valore del manifest: stringa semplice o {'it': ..., 'en': ...}."""
    if isinstance(value, dict):
        return value.get(lang) or value.get(DEFAULT_LANGUAGE) or next(iter(value.values()), '')
    return '' if value is None else str(value)
