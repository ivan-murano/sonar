# Prompt per la prossima chat (software Sonar)

Riprendi lo sviluppo del software Sonar (repository GitHub `ivan-murano/sonar`, ramo `main`; copia di lavoro non git sul mio PC in `D:\noise_pollution\outputs\sonar`). Leggi prima `README.md` (cos'è Sonar e come funziona il modello) e poi `docs/HANDOFF.md`, soprattutto §7 (ambienti di lavoro), §12 e §13 (stato attuale e prossimi passi). Il codice del modello in `D:\noise_pollution\src`, `scripts`, `configs`, `models` non va modificato; si possono eseguire i suoi script e launcher.

Non sono uno sviluppatore: fai tutto tu, file compresi. Comunica in italiano, in modo breve. Le schermate costano: controlla i risultati leggendo i file con `device_bash` e usa `zoom` su regioni piccole. I commit sono a nome di Ivan Murano, senza righe di attribuzione aggiuntive.

Stiamo preparando il GIS Day 2026 e vogliamo vincere il premio della giuria: i testi pubblici devono presentare bene il lavoro, restando veri.

Priorità:
1. Controlla la prova di Melfi con la popolazione GHSL (§13): totale residenti circa 17.000, tavola PNG e foglio xlsx in `Risultati\Popolazione esposta`.
2. Rifinisci la tavola A4 della popolazione esposta con la skill `schematic-figure` e riporta il disegno in `sonar_app/export/exposure_sheet.py`.
3. Porta avanti la validazione di Dublino (§13, punto 3).
4. Prepara una nuova release con l'installer aggiornato.
5. Aiutaci con la presentazione del GIS Day.

## Note pratiche

- Ricostruire e reinstallare: chiudere Sonar, doppio clic su `build\output\AAA_DIAG.cmd` (esito in `install_esito2.txt`, log in `build_log.txt`). L'installer si chiama `Sonar-Setup.exe`.
- La finestra dell'installer e la finestra «Apri» dell'app Claude non sono comandabili con l'uso del computer; nelle finestre di scelta cartella si naviga con i doppi clic.
- La VM `device_bash` non ha rete e non cancella file; per portare file dal contenitore al PC: `device_commit_files` con un percorso di staging nuovo ogni volta.
- Il contenitore non raggiunge il JRC (GHSL) né Sonitus: i download reali avvengono solo sul PC.
