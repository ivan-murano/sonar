## Sonar 1.1.0

**Installazione:** scaricare `Sonar-Setup.exe`, aprirlo, accettare la licenza: Sonar si installa per l'utente corrente (non servono diritti di amministratore né altri programmi: Python, Qt, GDAL e il modello sono inclusi) e si avvia. Modello incluso: *Pharos Noise* (stime sperimentali del rumore urbano). Si disinstalla da *Impostazioni → App*. Windows può mostrare l'avviso SmartScreen perché l'installer non è firmato digitalmente: *Ulteriori informazioni → Esegui comunque*.

**In breve:** si scrive il nome della città e Sonar consegna la mappa del rumore pronta per QGIS e ArcGIS: livello sonoro stimato ogni 100 m e su ogni strada, in sei fasce orarie per un giorno feriale e un festivo, con Lden e Lnight. Parigi in circa dieci minuti, città medie in pochi minuti, tutto sul proprio PC.

**Risultati:** GeoPackage e File Geodatabase con stili pronti (Lden indicativo predefinito, Lnight, LAeq per fascia), una tavola PNG per output con Lden e Lnight indicativi (giorno feriale e festivo), dati di input, licenza e fonti.

---

**Install:** download `Sonar-Setup.exe`, open it, accept the license: Sonar installs for the current user (no administrator rights or other software needed: Python, Qt, GDAL and the model are included) and starts. Included model: *Pharos Noise* (experimental urban noise estimates). Uninstall from *Settings → Apps*. Windows may show a SmartScreen warning because the installer is not digitally signed: *More info → Run anyway*.

**In short:** type a city name and Sonar delivers its noise map ready for QGIS and ArcGIS: estimated sound level every 100 m and on every road, in six time bands for a weekday and a holiday, with Lden and Lnight. Paris in about ten minutes, mid-size cities in a few minutes, all on your own PC.

**Results:** GeoPackage and File Geodatabase with ready styles (indicative Lden by default, Lnight, LAeq per time band), one PNG sheet per output with indicative Lden and Lnight (weekday and holiday), input data, license and sources.
