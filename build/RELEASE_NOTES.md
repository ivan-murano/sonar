## Sonar 1.0.0

**Installazione:** scaricare `Sonar-Setup-1.0.0.exe`, aprirlo, accettare la licenza: Sonar si installa per l'utente corrente (non servono diritti di amministratore né altri programmi: Python, Qt, GDAL e il modello sono inclusi) e si avvia. Modello incluso: *Pharos Noise* (stime sperimentali del rumore urbano). Si disinstalla da *Impostazioni → App*.

**Uso:** scrivere la città, premere *Avvia*, scegliere la cartella. Servono una connessione a internet (confini, OpenStreetMap, Overture, WorldCover) e, per una città come Napoli, circa 20 minuti e 1–2 GB di spazio per i download in cache.

Windows può mostrare l'avviso SmartScreen perché l'installer non è ancora firmato digitalmente: *Ulteriori informazioni → Esegui comunque*.

**Risultati:** GeoPackage e File Geodatabase con stili pronti (Lden indicativo predefinito, Lnight, LAeq per fascia), una tavola PNG per output con Lden e Lnight indicativi (giorno feriale e festivo), dati di input, licenza e fonti.

---

**Install:** download `Sonar-Setup-1.0.0.exe`, open it, accept the license: Sonar installs for the current user (no administrator rights or other software needed: Python, Qt, GDAL and the model are included) and starts. Included model: *Pharos Noise* (experimental urban noise estimates). Uninstall from *Settings → Apps*.

**Use:** type the city, press *Start*, choose the folder. An internet connection is required (boundaries, OpenStreetMap, Overture, WorldCover).

Windows may show a SmartScreen warning because the installer is not yet digitally signed: *More info → Run anyway*.

**Results:** GeoPackage and File Geodatabase with ready styles (indicative Lden by default, Lnight, LAeq per time band), one PNG sheet per output with indicative Lden and Lnight (weekday and holiday), input data, license and sources.

