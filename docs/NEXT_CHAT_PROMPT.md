# Prompt per la prossima chat (sviluppo del software Sonar)

Incollare il testo qui sotto come primo messaggio di una nuova chat, con la cartella `D:\noise_pollution` collegata e il repository `ivan-murano/sonar` disponibile.

---

Riprendi lo sviluppo del software **Sonar** (repository GitHub `ivan-murano/sonar`, copia di lavoro sul mio PC in `D:\noise_pollution\outputs\sonar`). Prima di tutto leggi `docs/HANDOFF.md` del repository: contiene architettura, stato, ambienti e problemi aperti. Il modello acustico è sviluppato in un'altra chat (vedi `docs/HANDOFF_MODEL.md`): non modificare il codice del modello in `D:\noise_pollution\src`, `scripts`, `configs`, `models`.

Non sono uno sviluppatore: fai tutto tu, file compresi. Da me servono solo approvazioni e, se proprio necessario, qualche clic che ti indico in modo preciso. Comunica in italiano.

Obiettivo di questa sessione: **una Release `v1.0.0` su GitHub con un `Sonar-Setup-1.0.0.exe` funzionante**, che chi lo scarica deve solo aprire per installare e usare Sonar, senza fare altro.

Passi:

1. **Correggere e verificare il build Windows.** L'installer attuale non funziona: la ricerca della città fallisce con "Servizio non raggiungibile", perché è stato costruito con il Python del runtime Codex, che impacchettato non crea connessioni HTTPS. `build\BUILD_WINDOWS.cmd` è già modificato per usare un Python 3.12 standard (launcher `py` oppure python-build-standalone via `uv` in `build\uv`), ma non è mai stato eseguito. Eseguilo sul mio PC: con l'uso del computer, apri Esplora file su `D:\noise_pollution\outputs\sonar\build` e fai doppio clic su `BUILD_WINDOWS.cmd`. Se un controllo di sicurezza ti blocca perché lo script scarica `uv` e Python da internet, chiedimi esplicitamente il permesso e procedi: lo autorizzo. Poi controlla `build\selftest.txt` (deve contenere `OK   rete (HTTPS)` e `ESITO: OK`) e `build\netdiag.txt`. Se HTTPS fallisce ancora, risolvi tu: le note di diagnosi sono in `docs/HANDOFF.md` §5.
2. **Provare l'installer come un utente.** Installalo (posso confermare io la licenza se me lo chiedi), apri Sonar, cerca "Melfi", premi Avvia e scegli una cartella di prova. Verifica che la consegna sia completa: GPKG con stile, File Geodatabase, PNG, dati di input, LEGGIMI, LICENZA, AUTORI. È la prima prova con i download reali (Geofabrik, Overture, WorldCover): correggi ciò che non va, ricostruisci e riprova.
3. **Pubblicare la Release `v1.0.0`** su `ivan-murano/sonar` allegando `build\output\Sonar-Setup-1.0.0.exe`, con le note in `build\RELEASE_NOTES.md`, aggiungendo lo SHA-256 del file finale. L'API GitHub di questa sessione ha rifiutato la creazione di release (HTTP 403): usa il browser integrato sul mio PC, dove GitHub è già collegato, oppure un'altra strada che funzioni. Il file supera 100 MB: non va messo nel repository.
4. Aggiorna `docs/HANDOFF.md` con i risultati reali, fai commit e push su un ramo e unisci in `main`, come nella sessione precedente.

Note pratiche (dettagli in `docs/HANDOFF.md` §7):
- Il contenitore cloud non raggiunge Nominatim, GISCO, Geofabrik, Overture e AWS: le prove di rete vanno fatte sul mio PC.
- Nella VM Linux del mio PC (`device_bash`) non si possono cancellare file, i comandi durano al massimo 180 s e i processi in background vengono chiusi. Per sovrascrivere usa `tar --overwrite`. `device_commit_files` memorizza i file per percorso di staging: per aggiornare un file già inviato usa un percorso di staging nuovo. Gli script `.cmd` devono avere fine riga CRLF.
- Logo e icona definitivi li fornirò più avanti: non crearne di nuovi.
