<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="sonar_app/assets/logo_dark.png">
    <img src="sonar_app/assets/logo_light.png" alt="Sonar" width="420">
  </picture>
</p>

<h3 align="center">
  <a href="https://github.com/ivan-murano/sonar/releases/latest/download/Sonar-Setup.exe">⬇ Scarica Sonar per Windows · Download Sonar for Windows</a>
</h3>
<p align="center"><code>Sonar-Setup.exe</code> · Windows 10/11 64 bit · circa 140 MB · <a href="https://github.com/ivan-murano/sonar/releases/latest">note di rilascio / release notes</a></p>

Mappe del rumore urbano ad alta risoluzione per le città europee, da dati aperti. Si scrive il nome della città, Sonar trova il confine comunale, scarica i dati che servono al modello, calcola le mappe e consegna una cartella ordinata con risultati, dati di input, licenza e autori.

*High-resolution urban noise maps for European cities from open data. Type a city, Sonar finds its municipal boundary, downloads the data the model needs, computes the maps and delivers an organised folder with results, input data, license and authors.*

## Installare

Aprire `Sonar-Setup.exe` (link qui sopra), accettare la licenza e Sonar è pronto: Python, Qt, GDAL e il modello sono inclusi, non servono diritti di amministratore né altri programmi. Windows può mostrare l'avviso SmartScreen perché l'installer non è firmato digitalmente: *Ulteriori informazioni → Esegui comunque*. Si disinstalla da *Impostazioni → App*.

Servono una connessione a internet, 1–2 GB di spazio per i download in cache e, secondo la dimensione della città, da un paio di minuti a circa 10 minuti di calcolo (Parigi, su un portatile con 12 thread).

## Uso

1. Avviare Sonar dal menu Start.
2. Scrivere la città e premere **Avvia** (o Invio per controllare prima il confine trovato). Se il nome indica più luoghi, Sonar chiede quale.
3. Scegliere la cartella di destinazione. Sonar mostra fase, avanzamento e cosa sta facendo; al termine compare **Apri cartella**.

Lingua (IT/EN) e tema (chiaro/scuro) si cambiano con gli interruttori in basso a destra; la lingua decide anche i nomi di cartelle e file della consegna.

## Cosa viene consegnato

```
Sonar_<Città>_<AAAA-MM-GG_HHMM>/
  Risultati/            (Results/)
    GeoPackage/         GPKG con stile QGIS già applicato
    File Geodatabase/   .gdb ESRI + Stili ArcGIS/*.lyrx
    Mappe/              (Maps/) tavole PNG
  Dati di input/        (Input data/)
    Confine/            confine LAU Eurostat GISCO
    OpenStreetMap/      estratto ritagliato sulla città
    Overture Places/    attività
    ESA WorldCover/     copertura del suolo
  LEGGIMI.txt  LICENZA.txt  AUTORI.txt  fonti_dati.json  registro.txt
```

## Fonti

- Ricerca della città: [Nominatim](https://nominatim.openstreetmap.org) (una richiesta per ricerca, nel rispetto della policy OSMF).
- Confini: [Eurostat GISCO LAU](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/local-administrative-units), © EuroGeographics, uso non commerciale.
- Dati del modello Pharos Noise: [OpenStreetMap](https://www.openstreetmap.org/copyright) via [Geofabrik](https://download.geofabrik.de), [Overture Maps Places](https://docs.overturemaps.org), [ESA WorldCover 2021](https://esa-worldcover.org).

## Modello

Il modello acustico è un modulo separato in `models/`, collegato al software dal contratto [`sonar-model/1`](docs/MODEL_CONTRACT.md): si può aggiornare o sostituire senza modificare Sonar. Il modello incluso è **Pharos Noise** (spiegazione: [docs/MODEL.md](docs/MODEL.md)): stima il livello sonoro esterno LAeq su celle H3 di circa 100 m e sui segmenti stradali, per giorno feriale e festivo e per sei fasce orarie. Sono stime sperimentali da dati aperti, senza misure locali di verifica: indicano dove e quando il rumore è plausibilmente più alto, non sostituiscono una mappatura acustica strategica. Passaggi di consegne: [software](docs/HANDOFF.md), [modello](docs/HANDOFF_MODEL.md).

## Sviluppo

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
set SONAR_MODEL_CODE=D:\noise_pollution          rem progetto del modello Pharos Noise
.venv\Scripts\python -m sonar_app                rem interfaccia
.venv\Scripts\python -m sonar_app --selftest     rem controllo dell'installazione
.venv\Scripts\python -m sonar_app.check_model    rem controllo dei pacchetti modello
.venv\Scripts\python -m pytest tests
```

`SONAR_LOCAL_INPUTS=<file.json>` con `{"osm_pbf": "...", "overture_places": "...", "esa_worldcover": "..."}` sostituisce i download con file locali.

Struttura: `sonar_app/places.py` (città e confine), `providers/` (download), `model_api.py` (contratto), `pipeline.py` (lavoro), `export/` (cartelle, GPKG, FileGDB, PNG, testi), `ui/` (interfaccia Qt 6), `worker.py` (processo di calcolo separato).

## Installazione Windows

Doppio clic su `build\BUILD_WINDOWS.cmd`: crea l'ambiente, esegue i test, costruisce `dist\Sonar\Sonar.exe` con PyInstaller, copia i modelli e le licenze, verifica l'eseguibile (`--selftest`) e, con [Inno Setup 6](https://jrsoftware.org/isinfo.php) (installato automaticamente con winget se manca), produce `build\output\Sonar-Setup-<versione>.exe`.

## Licenza

© 2026 Ivan Murano, Laura Ripoli. Uso gratuito, ridistribuzione non consentita: vedi [LICENSE.txt](LICENSE.txt). Componenti di terze parti: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
