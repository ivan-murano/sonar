# Passaggio di consegne — sviluppo del software Sonar

Stato al 14/11/2026, fine della sessione che ha creato Sonar 1.0.0. Scritto per chi riprende lo sviluppo del **software** (non del modello acustico: per quello vedi [HANDOFF_MODEL.md](HANDOFF_MODEL.md)).

## 1. Cosa vuole l'utente (Ivan Murano)

- Sonar è un **software desktop Windows** (Linux non serve più) per mappe del rumore urbano delle città europee. Autori del software e del modello: Ivan Murano e Laura Ripoli.
- Flusso: scrivere la città → geocoder → confine amministrativo da dataset europeo → **Avvia** → scelta della cartella → download di tutto ciò che il modello richiede → esecuzione del modello con avanzamento e descrizione del passo → **Apri cartella**.
- Consegna in cartelle ordinate, **nomi nella lingua scelta** (IT/EN): risultati in **PNG**, **GPKG già stilizzato**, **File Geodatabase ESRI**; dati di input; `LICENZA`, `AUTORI` (Ivan Murano, Laura Ripoli), `LEGGIMI` con link alla spiegazione del modello su GitHub.
- UI minimale e lineare, identica al mockup `outputs/sonar/ui/Sonar_tema_{chiaro,scuro}.png` nel progetto `D:\noise_pollution`. L'utente ha segnalato come "UI slop" la vecchia barra città+Avvia (pulsante rientrato nel bordo): ora è disegnata a mano e combacia col mockup. Selettore lingua IT/EN nello stesso stile dell'interruttore del tema.
- **Logo e icona definitivi arriveranno dall'utente**: il logo attuale è testo "Sonar" a contorno (Quicksand Bold). Ignorare l'icona della barra delle applicazioni finché non arriva.
- Requisito finale: chi scarica l'exe da GitHub **non deve fare altro che aprirlo** per installare e usare Sonar.
- Il **modello** è sviluppato in un'altra chat. Il software deve restare modulare: il modello si cambia senza rompere il software (contratto `sonar-model/1`).
- Comunicare in italiano; documentazione diretta e affermativa. Commit/push solo su richiesta (l'utente ha chiesto di caricare tutto sul repository).

## 2. Dove sta il codice

| Posizione | Contenuto |
|---|---|
| GitHub `ivan-murano/sonar` (privato), ramo `main` (PR #1 unita) e ramo `sonar-software` (commit successivi, da unire) | sorgente del software, contratto, adattatore M3, build |
| `D:\noise_pollution\outputs\sonar\` sul PC dell'utente | copia di lavoro **non git** del repository (estratta da tar), con `.venv-build`, `dist\Sonar`, `build\output\Sonar-Setup-1.0.0.exe`, `.diag\` (script di diagnosi temporanei), `_versione_precedente\` (vecchia app Qt monolitica, da ignorare), `ui\` (mockup) |
| `D:\noise_pollution\` | progetto del **modello** (pacchetto `sonar` in `src/sonar`, `scripts/`, `configs/`, `models/`, dati) |
| `D:\noise_pollution\SONAR_APP.cmd` | avvia il software da sorgente con la `.venv` del modello |

Attenzione al nome: il pacchetto del **software** è `sonar_app`; il pacchetto `sonar` è il **modello** (in `D:\noise_pollution\src\sonar`). Non rinominare.

## 3. Architettura

```
sonar_app/
  __init__.py      versione (__version__ = '1.0.0'), autori
  main.py          ingresso: UI, --worker <job.json>, --selftest [--offline], --netdiag, --version
  config.py        percorsi: install_dir, bundle_dir (_MEIPASS), models_dir (SONAR_MODELS_DIR | models/), user_data_dir
                   (%LOCALAPPDATA%\Sonar | SONAR_HOME), cache_dir, runs_dir, settings.json; REPOSITORY_URL, USER_AGENT
  i18n.py          tutte le stringhe UI (STRINGS), nomi cartelle (FOLDERS) e file (FILES) in it/en; t(), folder(), filename(), pick()
  net.py           requests con User-Agent e retry; ca_bundle() (certificati sempre esistenti); download con ripresa .part,
                   verifica MD5, limite dimensione, annullamento
  places.py        Nominatim search() (featureType=settlement, 1 richiesta/s, solo su conferma) e resolve_boundary():
                   servizio GISCO ID (https://gisco-services.ec.europa.eu/id/lau?x&y&proj=4326&year&format=geojson&geometry=yes),
                   anni 2024→2023→2021, ripiego sul file LAU 1:1M (catalogo lau-<anno>-files.json, nome file ipotizzato,
                   NON verificato). City dataclass (to_json/from_json, write_boundary GPKG)
  model_api.py     contratto sonar-model/1: ModelContext, Model (manifest, entrypoint caricato da file), validate_manifest,
                   validate_result, discover(), default_model()
  providers/       fornitori di dati, registry(): osm_pbf (Geofabrik index-v1.json + .md5 + ritaglio pyosmium),
                   overture_places (overturemaps.core.record_batch_reader, GeoParquet nativo), esa_worldcover (COG su S3,
                   finestra con rasterio.merge). SONAR_LOCAL_INPUTS = JSON {provider: file} sostituisce i download
  pipeline.py      run_job(spec, emit): cartella → confine → download → modello → export → testi; Reporter con fasi pesate
                   (prepare 0–2 %, download 2–35, model 35–90, export 90–100); la barra non torna indietro
  worker.py        processo di calcolo: legge job.json, scrive eventi "SONAR_EVENT {json}" su stdout (progress, folder, log,
                   done, error); ensure_streams() ricollega stdout nell'exe senza console
  export/__init__  make_root (Sonar_<Città>_<AAAA-MM-GG_HHMM>), export_results: GPKG + layer_styles (QML+SLD,
                   predefinito), File Geodatabase (driver OpenFileGDB) + .lyrx, PNG; write_sources (fonti_dati.json)
  export/styles.py qml() renderer graduato QGIS, sld(), lyrx() CIM ArcGIS Pro (ClassBreaksRenderer)
  export/maps.py   tavole PNG matplotlib (griglia fino a 2×3), titoli e piè di pagina localizzati
  export/docs.py   LEGGIMI/README, LICENZA/LICENSE (testo di LICENSE.txt + licenze dei dati), AUTORI/AUTHORS (CRLF + BOM)
  ui/widgets.py    disegno a mano: Frame (cornice 2 px), Logo, IconButton, SearchBar, PillToggle → ThemeToggle/LanguageToggle,
                   ProgressLine; font Quicksand statico 400/500/700 in assets/fonts
  ui/app.py        MainWindow (senza cornice, 640×360, trascinabile), Dialog, Task (QRunnable), lancio del worker con QProcess
  selftest.py      controllo dell'installazione (GDAL/FileGDB in scrittura, librerie, modello + codice, Qt, rete HTTPS)
  netdiag.py       diagnosi HTTPS passo per passo
  check_model.py   python -m sonar_app.check_model: verifica dei pacchetti modello
models/m3_barcellona/  sonar_model.json + adapter.py (vedi HANDOFF_MODEL.md)
build/             sonar.spec, sonar_entry.py, bundle_models.py, collect_licenses.py, version_info.txt, installer.iss,
                   BUILD_WINDOWS.cmd
tests/             15 test (contratto, export reale con GPKG/GDB/PNG, i18n, fornitori, Nominatim simulato, GISCO)
```

Flusso UI: Invio = cerca e mostra il confine trovato ("Napoli · IT · 119 km²" + "Confine LAU IT_063049 (Eurostat GISCO 2024)"); **Avvia** = cerca se serve, poi chiede la cartella e avvia. Se i candidati Nominatim sono ambigui (importanza simile o nome diverso dal digitato) compare una finestra di scelta nello stile dell'app. Il lavoro gira in un processo separato (`Sonar.exe --worker job.json`, da sorgente `python -m sonar_app.worker`), annullabile; eventi su stdout.

Impostazioni (`%LOCALAPPDATA%\Sonar\settings.json`): theme, language, last_city, last_folder. Cache: `...\Sonar\cache` (estratti Geofabrik regionali riusati, indice, tile). Cartelle di lavoro del modello: `...\Sonar\runs\<nome consegna>` (cancellate a lavoro riuscito). Errori: `...\Sonar\ultimo_errore.txt` (pulsante "Apri registro").

## 4. Consegna prodotta (verificata)

```
Sonar_Napoli_2026-11-14_0211/
  Risultati/GeoPackage/Napoli_rumore_celle_H3.gpkg (+ _metadata.json), Napoli_rumore_strade.gpkg
  Risultati/File Geodatabase/Napoli_Sonar.gdb (h3_feriale, h3_festivo, strade_feriale, strade_festivo)
  Risultati/File Geodatabase/Stili ArcGIS/*.lyrx
  Risultati/Mappe/*.png (una tavola per output e scenario, sei fasce)
  Dati di input/Confine, OpenStreetMap (PBF ritagliato), Overture Places, ESA WorldCover
  LEGGIMI.txt, LICENZA.txt, AUTORI.txt, fonti_dati.json, registro.txt
```

In inglese: `Results/…/Maps`, `Input data/Boundary`, `README.txt`, `LICENSE.txt`, `AUTHORS.txt`, `data_sources.json`, `log.txt`; layer `weekday`/`holiday`; file `Napoli_noise_H3_cells.gpkg`. I nomi dei file derivano da `file_stem` ed `export_name` nel manifest del modello.

## 5. Build e distribuzione Windows

- `build\BUILD_WINDOWS.cmd` (doppio clic, CRLF obbligatorio): trova il codice del modello (`%ROOT%\..\..` se il repository è in `D:\noise_pollution\outputs\sonar`, poi `D:\noise_pollution`, poi chiede) → crea `.venv-build` → `pip install -r requirements-build.txt` → `check_model` → `pytest` → PyInstaller (`build\sonar.spec`, cartella `dist\Sonar`) → `bundle_models.py` copia `models\` e il codice del modello (`code.bundle` del manifest) in `dist\Sonar\models\m3_barcellona\code` → licenze dei pacchetti in `dist\Sonar\licenses` → `Sonar.exe --selftest` (deve finire con `ESITO: OK`) e `--netdiag` → Inno Setup (`ISCC.exe`, installato per utente con winget se manca) → `build\output\Sonar-Setup-<versione>.exe`.
- Installer (`build\installer.iss`): per utente in `%LOCALAPPDATA%\Programs\Sonar`, niente diritti di amministratore, niente domande oltre alla licenza; collegamento nel menu Start, icona sul desktop facoltativa, avvio al termine. Compressione `lzma2/max` in processo separato (con `ultra64` ISCC va in "Out of memory").
- **Problema aperto principale (da verificare per primo):** il primo installer (14/11, 140 MB, SHA-256 `fde5dc63…d517`) è stato costruito con il Python del **runtime Codex** (`C:\Users\ivanm\.cache\codex-runtimes\...\python`, OpenSSL 3.5.8). Impacchettato con PyInstaller, quel Python non riesce a creare `ssl.SSLContext` (`FileNotFoundError [Errno 2]` dentro `SSLContext.__new__`, vedi `.diag\netdiag.txt`): la ricerca della città fallisce con "Servizio non raggiungibile". Da sorgente lo stesso Python funziona (Nominatim e GISCO rispondono). Non è un problema di certificati né di configurazione OpenSSL (provato `OPENSSL_CONF` vuoto). Correzione applicata nello script: `.venv-build` viene ricreata da un **Python 3.12 standard** (launcher `py` se presente, altrimenti python-build-standalone scaricato da `uv` in `build\uv`). Il build con questa correzione **non è ancora stato eseguito**: lanciare `BUILD_WINDOWS.cmd` e controllare `build\selftest.txt` (riga `OK rete (HTTPS)`) e `build\netdiag.txt`.
- **Release GitHub**: la sessione Claude non può creare release (HTTP 403 "not permitted for this session type"). L'utente deve creare la release `v1.0.0` da github.com e allegare `build\output\Sonar-Setup-1.0.0.exe` (oltre 100 MB: non va nel repository). Note di rilascio pronte nella risposta finale della sessione: installazione con un doppio clic, avviso SmartScreen (installer non firmato: "Ulteriori informazioni → Esegui comunque"). Il repository è privato: per scaricare serve l'accesso. Valutare una GitHub Action `windows-latest` che costruisce e pubblica l'installer al push di un tag (richiede che il codice del modello sia nel repository o scaricabile).
- Firma digitale del codice: assente. Eliminerebbe l'avviso SmartScreen; serve un certificato.

## 6. Verifiche fatte

- 15 test superati in Linux e su Windows (eseguiti dal build).
- Pipeline completa nell'app impacchettata Linux con dati locali di Napoli (`SONAR_LOCAL_INPUTS`): 18 min, consegna completa, PNG controllati a vista.
- Contratto + adattatore M3 con OSM **ritagliato** dal software: H3 identiche ai prodotti Windows di produzione (`D:\noise_pollution\outputs\gpkg\napoli_rumore_h3.gpkg`), differenza massima 2,8e-14 dB.
- Ritaglio OSM: 150 s per l'estratto Sud Italia (419 MB) → 11 MB per Napoli; conteggi del modello identici (45.856 strade, 108.741 edifici, 16.889 POI).
- `Sonar.exe --selftest` su Windows: GDAL 3.12.4 con FileGDB in scrittura, modello caricato dal codice incluso.
- Installer provato dall'utente sul suo PC: si installa e l'app si avvia; la ricerca di "Melfi" falliva per il problema TLS del punto 5.
- UI: schermate offscreen nei due temi e nelle due lingue; barra città confrontata pixel per pixel col mockup.
- Servizi reali dal PC dell'utente (da sorgente): Nominatim 200; GISCO ID restituisce `{"type":"FeatureCollection","features":[{"id":"IT_076048","properties":{"gisco_id":"IT_076048","lau_name":"Melfi"}}]}` con `geometry=no`. Le proprietà sono minuscole e poche: il codice ricava paese e codice LAU da `gisco_id`. Da verificare la risposta con `geometry=yes`.

**Non ancora verificati:** download reali Geofabrik/Overture/WorldCover dal PC; ripiego GISCO su file LAU (nomi ipotizzati); apertura degli stili in QGIS (`layer_styles`) e dei `.lyrx` in ArcGIS Pro (scritti secondo lo schema CIM senza ArcGIS per provarli); una città diversa da Napoli end-to-end; comportamento con città molto grandi (Overture `max_rows` 3 M, memoria del ritaglio OSM `sparse_mem_array` sotto 1,5 GB di PBF).

## 7. Ambienti di lavoro (cosa funziona dove)

- **Contenitore cloud** (`/home/claude`): Ubuntu 24.04, 2 CPU, 7 GB; `uv` disponibile; venv `/home/claude/venv` (Python 3.12.13 + dipendenze + PySide6 + PyInstaller). Qt offscreen funziona (`QT_QPA_PLATFORM=offscreen`) per schermate della UI. Rete: solo PyPI/GitHub; Nominatim, GISCO, Geofabrik, Overture, AWS **bloccati** (403 dal proxy). Clone del repository in `/home/claude/sonar`.
- **VM Linux sul PC dell'utente** (`device_bash`, `$HOME/mnt/noise_pollution` = `D:\noise_pollution`): Ubuntu 22.04, 3 GB, comandi al massimo 180 s, processi in background terminati a fine chiamata. Nessuna cancellazione (rm vietato senza permesso; `tar --overwrite` per sovrascrivere). `device_commit_files` **memorizza per percorso di staging**: per aggiornare lo stesso file usare un nuovo percorso in `/mnt/user-data/outputs/<cartella_nuova>/`. Niente libEGL: la UI Qt non parte lì.
- **Windows dell'utente**: si comanda solo con l'uso del computer, a livello "click" per Esplora file/terminale (niente digitazione). Per eseguire uno script: scriverlo nella cartella con device_bash e lanciarlo con doppio clic da Esplora file. L'esecuzione di script che scaricano ed eseguono programmi da internet può essere bloccata dal classificatore: in quel caso chiedere all'utente.
- Staging di file grandi verso il contenitore: massimo ~400 MB e timeout; per file più grandi `split` in parti da 100 MB.

## 8. Prossimi passi suggeriti

L'utente non è uno sviluppatore e non vuole toccare file: la prossima chat esegue tutto (build, prova dell'installer, release) chiedendo solo approvazioni. Prompt di avvio: [NEXT_CHAT_PROMPT.md](NEXT_CHAT_PROMPT.md).


1. Eseguire `BUILD_WINDOWS.cmd` con la correzione Python standard; verificare `selftest.txt`/`netdiag.txt`; reinstallare e cercare una città (es. Melfi) fino alla consegna.
2. Pubblicare la release v1.0.0 (manuale) o preparare la GitHub Action.
3. Logo e icona dell'utente: `sonar_app/assets/logo.svg` (letto in automatico da `Logo`) e `sonar_app/assets/sonar.ico` (usato da PyInstaller e dalla finestra); aggiungere `SetupIconFile` in `installer.iss`.
4. Provare gli stili in QGIS e ArcGIS Pro; eventualmente regola "nessuna stima" grigia anche in QGIS (ora i NULL non sono disegnati).
5. Gestire città fuori copertura GISCO e senza estratto Geofabrik con messaggi chiari; un'opzione "confine da file".
6. Unire `sonar-software` in `main` dopo le verifiche.
