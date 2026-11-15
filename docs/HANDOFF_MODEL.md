# Passaggio di consegne — sviluppo del modello GIS del rumore (per Sonar)

Stato al 14/11/2026. Scritto per la chat che continua lo sviluppo del **modello** di inquinamento acustico (progetto `D:\noise_pollution`). Il software Sonar è separato: questo documento spiega che cosa il software si aspetta dal modello, che cosa gli fornisce e cosa è stato verificato. Una copia è in `D:\noise_pollution\docs\handoff\sonar_modello.md`.

## 1. Principio

- Il **software** (repository `ivan-murano/sonar`, copia locale `D:\noise_pollution\outputs\sonar`, pacchetto `sonar_app`) trova la città, scarica i dati, crea le cartelle di consegna, stilizza ed esporta (GPKG, File Geodatabase, PNG), scrive licenza/autori/istruzioni e gestisce la UI.
- Il **modello** (questo progetto, pacchetto `sonar` in `src/sonar`, più `scripts/`, `configs/`, `models/`) riceve file locali e restituisce GeoPackage. È collegato al software da un **adattatore** e da un **manifest** secondo il contratto `sonar-model/1`: [`docs/MODEL_CONTRACT.md`](MODEL_CONTRACT.md) nel repository del software.
- Finché il contratto è rispettato, il modello si cambia senza toccare il software. Il software non va modificato da questa chat: se serve un nuovo tipo di dato o un nuovo formato di uscita, va chiesto a chi sviluppa il software.

## 2. Il collegamento attuale (modello M3)

`outputs/sonar/models/m3_barcellona/` (nel repository del software):

- `sonar_model.json`: id `m3_barcellona`, versione `1.0.0`, `documentation_url` = `https://github.com/ivan-murano/sonar/blob/main/docs/MODEL.md` (file oggi segnaposto: **va scritta la spiegazione del modello**, è il link che finisce in LEGGIMI.txt e AUTORI.txt di ogni consegna).
- `inputs`: `osm` (provider `osm_pbf`, buffer 1500 m + margine di ritaglio 1000 m), `places` (`overture_places`, buffer 1500 m), `landcover` (`esa_worldcover`, buffer 1500 m). I buffer sono attorno al confine LAU e coprono il contesto di 1 km usato da `acquire`.
- `outputs`: `h3` e `strade`, ciascuno con layer `feriale`/`festivo`; stile `laeq` (classi 40–80 dB(A) ogni 5 dB, 10 colori); `style_field` = `laeq_09_13`; `map_fields` = le sei fasce `laeq_00_06 … laeq_21_24`.
- `code.bundle`: file del progetto del modello copiati nell'installazione: `src/**/*.py`, `scripts/**/*.py`, `configs/**/*`, `models/20261013T133952Z_activity_hours/*_M3.joblib`, `.../programs.json`, `data/processed/20261013T084848Z_reference_dataset/site_features.parquet`. **Se il modello usa nuovi file (modelli, configurazioni, tabelle), vanno aggiunti qui**, altrimenti l'installazione non li contiene.
- `notes` e `output_license` (it/en): testi che finiscono in LEGGIMI e LICENZA; aggiornarli quando cambia il significato dei risultati.
- `adapter.py`: `run(ctx)` imposta `SONAR_CODE` (radice del codice) e `SONAR_ROOT` (cartella di lavoro), mette `scripts/` e `src/` nel path, poi esegue `sonar.acquire.run_acquire` **da file locali** (`--boundary`, `--country`, `--osm-pbf`, `--places`, `--worldcover`), `run_prepare`, `run_predict` e restituisce i due GPKG di `outputs/cities/<città>/<run>/`. Converte i codici paese GISCO `EL`→`GR`, `UK`→`GB` per le festività. L'avanzamento riconosce i messaggi `k/n Descrizione` e i contatori `x / y` del modello: **mantenere quel formato nei log** per avere una barra sensata.

## 3. Cosa riceve il modello

| File | Origine | Note |
|---|---|---|
| confine (`ctx.boundary`, GPKG EPSG:4326) | Eurostat GISCO LAU (2024, poi 2023, 2021) | attributi `name, lau_name, lau_id, gisco_id, country, lau_year, area_km2`; licenza non commerciale EuroGeographics |
| PBF OSM ritagliato | estratto Geofabrik più piccolo che copre l'area, verificato con MD5 | oggetti con tag nel riquadro (confine + 2,5 km), vie complete con i nodi fuori riquadro, multipoligoni che usano quegli oggetti; nodi senza tag fuori dalle vie esclusi |
| Overture Places | ultima release STAC, GeoParquet nativo (`overturemaps.core.record_batch_reader`) | stesso schema dei download del progetto |
| ESA WorldCover 2021 v200 | finestra dei COG su S3 (o tile intera in cache) | GeoTIFF deflate tiled, nodata 0 |

`ctx.city` contiene `name, country_code (GISCO), lat, lon, lau_id, gisco_id, lau_name, lau_year, area_km2, population`.

## 4. Verifiche fatte il 14/11/2026

- Con il PBF ritagliato da Sonar, `prepare` legge esattamente gli stessi oggetti della produzione: 45.856 strade, 108.741 edifici, 16.889 POI.
- Pipeline completa via contratto (contenitore Ubuntu 24.04, Python 3.12.13, CPU con AVX-512): le H3 feriale e festivo coincidono con `outputs/gpkg/napoli_rumore_h3.gpkg` di produzione (Windows): differenza massima 2,8e-14 dB, 0 celle diverse su 7.518. Tempo: 17 min (prepare ~14, predict ~1,5).
- **D057 (differenza Windows/Linux):** la stessa pipeline nella VM Ubuntu 22.04 (glibc 2.35, senza AVX-512) dava 681 celle diverse fino a 0,7 dB. La differenza dipende dall'ambiente matematico (CPU/libreria matematica), **non dal sistema operativo né dal codice**. Strumento: `scripts/diagnose_platform_features.py` e `DIAGNOSI_PIATTAFORMA.cmd`; nel campione ogni riga ha feature esattamente sulle soglie degli alberi HGB (`open_all_500/250`, `hour_sin`, `open_restaurant_500`, `open_retail_500`). Una mitigazione (es. quantizzazione delle feature prima di `predict`) cambierebbe alcune previsioni rispetto ai prodotti esistenti: è una decisione del modello.

## 5. Come si cambia il modello senza rompere Sonar

1. Modificare il codice del modello in questo progetto.
2. Se cambiano chiamate, nomi dei file prodotti, layer o campi: aggiornare `outputs/sonar/models/m3_barcellona/adapter.py` e `sonar_model.json` (`version`, `outputs`, `map_fields`, `style_field`, `styles`, `notes`, `code.bundle`). Per un modello del tutto nuovo: nuova cartella in `outputs/sonar/models/<id>/` con `"default": true`.
3. Regole del contratto: `run(ctx)` restituisce `{"outputs": {output_id: Path GPKG}, "metadata": {...}}`; ogni GPKG contiene i layer dichiarati; geometrie poligoni o linee; i campi di `map_fields` devono esistere; niente download da internet nel modello (dichiarare i dati in `inputs`); scrivere solo in `ctx.work_dir`/`ctx.output_dir`; niente import di Qt o di `sonar_app`.
4. Verificare: dalla cartella `outputs/sonar`, `python -m sonar_app.check_model` (manifest ed entrypoint) e `python -m pytest tests`.
5. Prova completa senza rete con dati locali: creare un JSON `{"osm_pbf": "...pbf", "overture_places": "...parquet", "esa_worldcover": "...tif"}`, impostare `SONAR_LOCAL_INPUTS` a quel file e `SONAR_MODEL_CODE=D:\noise_pollution`, poi lanciare la UI (`SONAR_APP.cmd`) o il worker con un job JSON (`python -m sonar_app.worker job.json`, schema: `{"city": City.to_json(), "out_dir": "...", "language": "it"}`).
6. Ricostruire l'installazione: `outputs\sonar\build\BUILD_WINDOWS.cmd` (copia il codice secondo `code.bundle`).

## 6. Cose da sapere sul codice del modello

- Le sessioni del software hanno modificato in passato alcuni file del modello (11/11): `src/sonar/runs.py` (`CODE_ROOT` da `SONAR_CODE` o da `sys._MEIPASS` nell'eseguibile: **indispensabile** perché il modello funzioni dentro l'installazione), `src/sonar/places.py` (`pad_programs`: profili di attività assenti a conteggio nullo, usato da `predict` e `points`), `src/sonar/cli.py` (`--events`, `--out`, `--interactive` su acquire, stage `maps`), `src/sonar/maps.py`. Il 14/11 nessuna modifica al modello. Conservare `SONAR_CODE`/`SONAR_ROOT` in `runs.py`.
- L'adattatore usa `sonar.cli.parser()` per costruire gli argomenti degli stage: se cambiano nomi o significati degli argomenti di `acquire`/`prepare`/`predict`, aggiornare l'adattatore.
- Calendario scolastico: senza file viene assunto (flag `SCHOOL_CALENDAR_ASSUMED`). Sonar non passa un calendario: se il modello ne vuole uno per paese, può leggerlo dai propri `configs/` in base a `ctx.city['country_code']`.
- `population`/`exposure` e `points` esistono nel modello ma **non sono collegati a Sonar**. Per collegarli: dichiarare nuovi `inputs` (servono nuovi fornitori nel software: GHSL, ISTAT, Eurostat) e nuovi `outputs`.
- Tempi e memoria: Napoli ~17 min su 2 CPU; il passo più lento sono le feature statiche dei ~106.700 ricevitori. Una città grande moltiplica i tempi: utile ridurre o parallelizzare.
- `predict` scrive anche `*_metadata.json` accanto ai GPKG: Sonar li copia nella consegna come `<file>_metadata.json`.
- Python del runtime Codex: impacchettato con PyInstaller non riesce a creare connessioni HTTPS (problema del software, non del modello), per questo il build ora usa un Python 3.12 standard. La `.venv` del progetto del modello resta quella di prima.

## 7. Stato scientifico (dal progetto del modello)

Vedi `docs/STATUS.md`, `docs/DECISIONS.md` (D054–D058), `docs/handoff/city_tool.md`, `docs/handoff/sonar_software.md`. In breve: cinque M3 di Barcellona in media energetica, stime sperimentali senza misure locali di verifica, H3 R10 e strade, sei fasce, feriale/festivo; verifica interurbana Dublino e popolazione/esposizione Napoli ancora da eseguire con i download reali; spiegazione pubblica del modello (`docs/MODEL.md` del repository del software) da scrivere.

## 8. Richieste del software al modello (14/11/2026)

- **Livello minimo e soglie sanitarie.** Su Melfi le stime hanno un pavimento per fascia (es. 48,0–48,4 dB 00–06, ~53 dB di giorno) anche in aperta campagna: ne derivano Lden indicativo ≈ 57,8 e Lnight ≈ 50,5 dB ovunque, cioè il 100% del territorio sopra le soglie OMS (53/45) e UE (55/50). Per questo Sonar usa la scala `"city"` e dichiara che i valori non vanno confrontati con le soglie OMS. Se il modello potrà fornire livelli confrontabili (scala in facciata, pavimento realistico), basta impostare `"scale": "who"` in `indicators` del manifest.
- **Indicatori.** Sonar calcola Lden/Lnight indicativi dalle sei fasce (vedi `MODEL_CONTRACT.md`, `indicators`). Le fasce non coincidono con i periodi della Direttiva (07–19/19–23/23–07): ogni ora prende il valore della sua fascia. Se il modello producesse direttamente i livelli orari o per periodo, la stima sarebbe più fedele.
- **Nome visibile.** Il modello non ha un nome pubblico proprio: in tutto ciò che vede l'utente compare come «modello acustico di Sonar» (EN «Sonar acoustic model»). Restano "M3"/"Barcelona" nei testi prodotti dal codice del modello: righe del registro (es. «Programmi di apertura delle attività (M3)») e `*_metadata.json` (`model_id`, `target`, `model_ensemble`, `validation`). Da allineare nel modello quando opportuno.

## 9. Feature statiche accelerate dal software (14/11/2026)

Nelle città grandi la fase «4/6 Feature statiche 100/250/500 m» era la più lunga (Parigi: ore). Causa: in
`src/prediction_features.py` ogni coppia ricevitore-geometria passa per `covered_by` e, se a cavallo del bordo,
per un'intersezione GEOS con il buffer a 64 lati (~15 µs di costo fisso per chiamata), su 2-3 thread.

Sonar ora usa `sonar_app/fastfeatures.py` (stesse definizioni, nessun file del modello modificato): l'adattatore
sostituisce a runtime `sonar.prepare.compute_static_features`. La funzione mantiene interfaccia, cache a blocchi e
verifica: a ogni esecuzione confronta 100 ricevitori con `reference_features_function()` del modello
(`np.allclose`, rtol 1e-10, atol 1e-7) e si ferma se differiscono. Calcolo: una sola interrogazione dell'indice per
strato, misura intera per le geometrie con bbox nel cerchio inscritto del 64-gono, ritaglio vettoriale (numpy) con i
lati del 64-gono dello spicchio che contiene la geometria, processi paralleli (circa i core fisici, entro la memoria).

Misure (Napoli, dati di `20261111T141457Z_sonar_prepare_napoli`): differenza massima dal riferimento 9e-9; un core:
6,8 → 1,2 ms per ricevitore (centro storico 11,5 → 1,8). `SONAR_FAST_FEATURES=0` ripristina il calcolo originale.
**Proposta**: adottare il metodo in `src/prediction_features.py` / `prepare.py`; se le feature cambiano, la verifica a
ogni esecuzione segnala subito la differenza e Sonar va aggiornato.
