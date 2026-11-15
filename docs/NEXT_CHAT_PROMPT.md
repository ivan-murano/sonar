# Prompt per la prossima chat (software Sonar)

Riprendi lo sviluppo del software Sonar (repository GitHub `ivan-murano/sonar`, ramo `main`; copia di lavoro non git sul mio PC in `D:\noise_pollution\outputs\sonar`). Leggi prima `docs/HANDOFF.md` (§7, §9, §10 e §12: ambienti, ostacoli e stato). Il modello acustico è sviluppato in un'altra chat: non modificare `D:\noise_pollution\src`, `scripts`, `configs`, `models`; le richieste al modello vanno in `docs/HANDOFF_MODEL.md`.

Non sono uno sviluppatore: fai tutto tu, file compresi. Comunica in italiano, in modo breve. Le schermate costano: controlla i risultati leggendo i file con `device_bash` e usa `zoom` su regioni piccole.

## Stato

- Release `v1.1.0` con l'installer `Sonar-Setup.exe` (link diretto in cima al README). Parigi completa in circa 10 minuti (HANDOFF §12). Il modello si chiama *Pharos Noise*.
- Le mappe PNG sono una tavola di sintesi per output con Lden e Lnight indicativi (somma energetica delle fasce), scala in dB adattata alla città. Le classi OMS sono pronte (`"scale": "who"` nel manifest) ma spente finché il modello non fornisce valori confrontabili con le soglie.

## Possibili passi successivi

1. Provare gli stili in QGIS e ArcGIS Pro (Lden predefinito, Lnight, LAeq).
2. Quando la chat del modello aggiorna il pavimento dei valori: valutare `"scale": "who"`.
3. Città fuori copertura GISCO o senza estratto Geofabrik: messaggi chiari, opzione "confine da file".
4. Firma digitale dell'installer (avviso SmartScreen).

## Note pratiche

- Ricostruire e reinstallare: doppio clic su `build\output\AAA_DIAG.cmd` (esito in `install_esito2.txt`, log in `build_log.txt`); chiudere prima l'app Sonar.
- La finestra dell'installer e la finestra «Apri» dell'app Claude non sono comandabili con l'uso del computer; nelle finestre di scelta cartella si naviga con i doppi clic.
- La VM `device_bash` non ha rete e non cancella file; per portare file dal contenitore al PC: `device_commit_files` con un percorso di staging nuovo ogni volta.
