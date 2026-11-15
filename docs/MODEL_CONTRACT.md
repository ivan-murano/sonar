# Contratto modello `sonar-model/1`

Documento per chi sviluppa il modello acustico. Sonar (il software) e il modello sono separati: il modello si può cambiare liberamente finché rispetta questo contratto, e il software continua a funzionare senza modifiche.

## Divisione dei compiti

| Sonar (software) | Modello |
|---|---|
| ricerca della città (Nominatim) e confine LAU Eurostat GISCO | calcolo dei livelli dai file ricevuti |
| download dei dati dichiarati nel manifest, cache, verifica | scrittura dei risultati in GeoPackage |
| cartelle di consegna, nomi nella lingua scelta (IT/EN) | dichiarazione di layer, campi da mappare, classi e colori |
| GPKG con stile QGIS, File Geodatabase + `.lyrx` ArcGIS, PNG | testi propri: note di lettura e licenza dei risultati |
| licenza, autori, LEGGIMI, fonti, registro, avanzamento in UI | messaggi di avanzamento tramite `ctx.progress` |

Il modello non importa Qt né moduli di `sonar_app` diversi dal contesto ricevuto, non scarica dati da internet e scrive solo in `ctx.work_dir` / `ctx.output_dir`.

## Pacchetto modello

Una cartella in `models/` (nell'installazione: `models/` accanto a `Sonar.exe`):

```
models/<id>/
  sonar_model.json   manifest (obbligatorio)
  adapter.py         modulo con la funzione indicata in "entrypoint"
  code/              facoltativo: codice e file del modello inclusi dalla build ("code.bundle")
```

Se nella cartella `models/` ci sono più pacchetti, Sonar usa quello con `"default": true`.

## Manifest `sonar_model.json`

Esempio completo: [`models/m3_barcellona/sonar_model.json`](../models/m3_barcellona/sonar_model.json).

| Campo | Significato |
|---|---|
| `contract` | sempre `"sonar-model/1"` |
| `id`, `version` | identificativo stabile e versione del modello |
| `default` | `true` per il modello predefinito |
| `name` | `{"it": ..., "en": ...}`, mostrato in UI, PNG e documenti |
| `authors` | elenco degli autori del modello (va in AUTORI.txt) |
| `documentation_url` | link alla spiegazione del modello (va in LEGGIMI.txt e AUTORI.txt) |
| `entrypoint` | `"modulo:funzione"`, relativo alla cartella del pacchetto |
| `code` | facoltativo: `env` (variabile con la radice del codice in sviluppo), `bundled_dir` (sottocartella nell'installazione), `bundle` (glob, relativi alla radice del codice, da copiare nella build) |
| `inputs` | dati da scaricare, vedi sotto |
| `outputs` | prodotti, vedi sotto |
| `styles` | stili a classi usati dagli output |
| `notes` | `{"it", "en"}`: come leggere i risultati (LEGGIMI.txt) |
| `output_license` | `{"it", "en"}`: licenza dei risultati (LICENZA.txt) |

### `inputs`

Ogni voce: `{"id": "<nome per il modello>", "provider": "<fornitore>", ...parametri}`. Il modello riceve `ctx.inputs["<id>"]` = percorso del file.

| `provider` | File consegnato | Parametri |
|---|---|---|
| `osm_pbf` | `.osm.pbf` ritagliato: oggetti con tag nel riquadro, vie complete, multipoligoni (fonte: estratto Geofabrik più piccolo che copre l'area, verificato con MD5) | `buffer_m` (default 1000), `clip_margin_m` (default 1000) |
| `overture_places` | GeoParquet Overture nativo, ultima release STAC | `type` (default `place`), `buffer_m`, `release`, `max_rows` |
| `esa_worldcover` | GeoTIFF WorldCover 2021 v200, 10 m | `buffer_m`, `margin_deg` |

Il riquadro è quello del confine LAU allargato di `buffer_m` metri. Un nuovo tipo di dato richiede un nuovo fornitore in `sonar_app/providers/` (lavoro del software: chiedere).

### `outputs`

```json
{"id": "h3", "title": {"it": "Celle H3", "en": "H3 cells"},
 "file_stem": {"it": "rumore_celle_H3", "en": "noise_H3_cells"},
 "layers": [{"name": "feriale", "export_name": {"it": "feriale", "en": "weekday"}, "title": {"it": "...", "en": "..."}}],
 "style": "laeq", "style_field": "laeq_09_13",
 "map_fields": [{"field": "laeq_00_06", "title": {"it": "00–06", "en": "00–06"}, "hours": [0, 6]}],
 "optional": false}
```

- `layers[].name`: nome del layer nel GeoPackage del modello; `export_name` il nome nella consegna.
- `style_field`: campo usato dallo stile predefinito in QGIS e ArcGIS.
- `map_fields`: campi dei livelli per fascia oraria; `hours` = ore [inizio, fine) della fascia (serve agli indicatori).
  Senza `indicators`: un riquadro PNG per campo (fino a 6 per tavola: griglia 2×3), una tavola per layer.
- Geometrie: poligoni o linee; il CRS è libero (metrico consigliato).

### `styles`

```json
"laeq": {"title": {"it": "LAeq stimato", "en": "Estimated LAeq"}, "unit": "dB(A)",
         "breaks": [40, 45, 50, 55, 60, 65, 70, 75, 80],
         "colors": ["#ffffcc", "...10 colori in tutto..."], "no_data_color": "#d5d9dc"}
```

`colors` ha un elemento in più di `breaks`: prima classe `< breaks[0]`, ultima `≥ breaks[-1]`.

### `indicators` (facoltativo)

```json
"indicators": {"items": ["lden", "lnight"], "scale": "city", "clip": [5, 98], "max_classes": 8}
```

Se presente, e se `map_fields[].hours` coprono le 24 ore, Sonar calcola per ogni elemento **Lden** e **Lnight indicativi**
(campi `lden_ind`, `lnight_ind`) con somma energetica delle fasce (10^(L/10), mai media aritmetica dei dB): Lden secondo la
Direttiva 2002/49/CE (giorno 07–19, sera 19–23 +5 dB, notte 23–07 +10 dB), Lnight = LAeq 23–07. Ogni ora prende il valore
della fascia che la contiene. Effetti nella consegna:

- GPKG: stili Lden (predefinito), Lnight e lo stile `style` su `style_field`; `.lyrx` su Lden;
- PNG: **una tavola per output** (righe = layer, colonne = indicatori), al posto delle tavole per fascia; con `"scale": "city"`
  una sola scala di colori e una sola legenda per tutte le mappe della tavola.

`scale`: `"city"` = classi a passi regolari in dB (1, 2, 2,5, 5 o 10 dB, al massimo `max_classes`) tra i percentili `clip`
dei valori della città: negli stili dei layer una scala per indicatore su tutti i layer e gli output, nelle tavole PNG una
scala unica calcolata con la stessa regola sui valori di tutti i riquadri della tavola (Lden e Lnight, feriale e festivo); `"who"` = classi fisse ancorate alle
soglie OMS 2018 per il traffico stradale (53 dB Lden, 45 dB Lnight) e alle classi di 5 dB della Direttiva. Usare `"who"`
solo quando i valori del modello sono confrontabili con livelli in facciata (oggi non lo sono: vedi `HANDOFF_MODEL.md`);
con `"who"` la tavola PNG ha una legenda per colonna.

## Funzione `run(ctx)`

```python
def run(ctx) -> dict:
    ctx.city        # dict: name, country_code (codice GISCO: EL=Grecia, UK=Regno Unito), lat, lon,
                    #       lau_id, gisco_id, lau_name, lau_year, area_km2, population
    ctx.boundary    # Path: GeoPackage EPSG:4326 con il confine LAU
    ctx.inputs      # dict id -> Path dei file scaricati
    ctx.work_dir    # Path: cartella di lavoro (cancellata a fine lavoro riuscito)
    ctx.output_dir  # Path: cartella suggerita per i GeoPackage prodotti
    ctx.language    # 'it' | 'en'
    ctx.model_dir   # Path della cartella del pacchetto
    ctx.progress(fraction, message)   # fraction 0..1; message stringa o {'it': ..., 'en': ...}
    ctx.log(text)                     # registro dettagliato (registro.txt)
    ctx.cancelled()                   # True se l'utente ha interrotto
    return {"outputs": {"h3": Path(...), "strade": Path(...)},   # un GeoPackage per output id
            "metadata": {...}}                                     # libero, finisce in fonti_dati.json
```

Sonar verifica che ogni output non facoltativo esista e contenga i layer dichiarati. I file `<nome_gpkg>*.json` accanto al GeoPackage vengono copiati nella consegna. Le eccezioni sollevate da `run` diventano un errore in UI con il registro completo.

## Come cambiare il modello

1. Aggiornare il codice del modello nel suo progetto.
2. Aggiornare `models/<id>/adapter.py` se cambiano chiamate o file prodotti.
3. Aggiornare `sonar_model.json`: `version`, eventuali nuovi `inputs`, `outputs`, `styles`, `code.bundle`.
4. Provare: `python -m sonar_app.check_model` (verifica il manifest) e un'esecuzione con dati locali (vedi `tests/test_model_contract.py`).
5. Ricostruire l'installazione (`build\BUILD_WINDOWS.cmd`).

Per un modello del tutto nuovo basta una nuova cartella in `models/` con `"default": true`.
