# Prompt per la prossima chat (software Sonar)

Riprendi lo sviluppo del software Sonar (repository GitHub `ivan-murano/sonar`, copia di lavoro non git sul mio PC in `D:\noise_pollution\outputs\sonar`). Prima di tutto leggi `docs/HANDOFF.md` (soprattutto §7 e §9: ambienti, ostacoli già incontrati e come aggirarli) e lavora sul ramo `fix-lookup-thread`, che contiene l'ultima correzione e va unito in `main`. Il modello acustico è sviluppato in un'altra chat: non modificare `D:\noise_pollution\src`, `scripts`, `configs`, `models`.

Non sono uno sviluppatore: fai tutto tu, file compresi. Da me servono solo approvazioni e, se indispensabile, qualche clic indicato in modo preciso. Comunica in italiano, in modo breve.

**Consumo:** le schermate sono la voce più costosa. Controlla i risultati leggendo i file con `device_bash`; usa l'uso del computer solo per avviare script con doppio clic e per la prova nell'app, con `zoom` su regioni piccole invece di schermate intere. Non rileggere file già letti.

## Stato

- Build Windows verificato (Python 3.12 standalone via `uv`): HTTPS funziona, `selftest` OK.
- Corretto il blocco della ricerca città (thread dell'interfaccia). Installer ricostruito e installato sul mio PC: `build\output\Sonar-Setup-1.0.0.exe`.
- Ho provato io Melfi fino in fondo: ha funzionato. La cartella di consegna è quella che ho scelto durante la prova (chiedimi il percorso se non la trovi in `D:\noise_pollution`).

## Da fare, in ordine

1. **Nome del modello: "Pharos Noise".** In tutto ciò che l'utente vede (LEGGIMI/README, LICENZA, AUTORI, titoli e piè di pagina delle mappe PNG, metadati, note di rilascio, `docs/MODEL.md`, README) il modello si chiama solo *Pharos Noise*: niente "M3", niente "Barcellona". `m3_barcellona` resta come identificativo interno e nome di cartella. Il campo `name` del manifest è già cambiato: cerca e allinea il resto (`notes`, `output_license`, testi in `sonar_app/export/docs.py` e `maps.py`, `i18n.py`).
2. **Controllo della consegna di Melfi** file per file: GPKG con stile (`layer_styles`), File Geodatabase con i quattro layer e i `.lyrx`, PNG, dati di input, LEGGIMI, LICENZA, AUTORI, `fonti_dati.json`. Correggi ciò che non va.
3. **Legenda delle mappe** (vedi sotto): prepara la proposta con un esempio su Melfi e fammela approvare prima di cambiare il comportamento predefinito.
4. **Ricostruisci e reinstalla** con `build\output\AAA_DIAG.cmd` (doppio clic; esito in `install_esito2.txt`, log in `build_log.txt`), ripeti la prova rapida con Melfi.
5. **Release `v1.0.0`** su `ivan-murano/sonar` dal browser integrato del mio PC (l'API della sessione rifiuta le release con 403): allega `Sonar-Setup-1.0.0.exe`, note da `build\RELEASE_NOTES.md` più lo SHA-256 del file finale. Il file supera 100 MB: non va nel repository. Chiedimi conferma prima di pubblicare.
6. **Chiusura:** aggiorna `docs/HANDOFF.md` con i risultati reali, commit e push, unisci in `main`, allinea la copia sul PC.

## Legenda delle mappe: problema e proposta

Con la scala fissa 40–80 dB(A) a passi di 5 dB le strade urbane risultano tutte rosse e il territorio rurale bianco: la mappa PNG non mostra le differenze dentro l'area costruita, che è dove il rumore conta. La scala è dichiarata nel manifest del modello (`styles.laeq`) ma è applicata dal software (`export/styles.py`, `export/maps.py`): la soluzione sta nel software, con un'opzione del contratto, senza toccare il codice del modello.

Proposta da valutare:
- **Due letture, due stili.** *Assoluta*: la scala fissa attuale, confrontabile tra città. *Relativa* ("contrasto locale"): classi calcolate dai risultati della città.
- **Classi relative**: quantili (8–10 classi) dei valori compresi tra il 5° e il 95° percentile, calcolati sui soli elementi dell'area costruita (tutti i segmenti stradali; per le H3 le celle che contengono strade o edifici, oppure sopra una soglia minima), con limiti arrotondati a 0,5 dB. Le code finiscono nelle classi estreme ("< x", "> y").
- **Una sola scala per città**: stessi limiti per le sei fasce e per feriale/festivo, così le tavole restano confrontabili tra loro (calcolo sull'insieme di tutti i campi `map_fields`).
- **Tavole PNG**: predefinita la relativa, con in legenda i valori in dB(A) e la dicitura "scala adattata alla città"; l'assoluta come seconda tavola o cartella separata.
- **GIS**: nel GPKG entrambi gli stili in `layer_styles` (predefinito da decidere); `.lyrx` analoghi.
- **Contratto**: nel manifest, per esempio `"styles": {"laeq": {..., "relative": {"method": "quantile", "classes": 9, "clip": [5, 95]}}}`; se manca, resta il comportamento attuale. Documentare in `docs/MODEL_CONTRACT.md` e avvisare la chat del modello tramite `docs/HANDOFF_MODEL.md`.
- Alternativa più semplice da confrontare: scala fissa più fine (passi di 2 dB tra 50 e 75) con tavolozza percettivamente uniforme.

## Note pratiche

- La finestra dell'installer non è comandabile con l'uso del computer: installare con lo script silenzioso. Nella finestra di scelta cartella non si può digitare: navigare con i doppi clic.
- La VM `device_bash` non ha rete, non cancella file (sovrascrivere va bene), comandi al massimo 180 s. Gli script `.cmd` richiedono fine riga CRLF.
- Per portare file dal contenitore al PC: `device_commit_files` con un percorso di staging nuovo ogni volta sotto `/mnt/user-data/outputs/<cartella_nuova>/`.
- Logo e icona definitivi li fornisco io più avanti: non crearne.
