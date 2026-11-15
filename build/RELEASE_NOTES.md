## Sonar 1.1.0

**Installazione:** scaricare `Sonar-Setup.exe`, aprirlo, accettare la licenza: Sonar si installa per l'utente corrente (non servono diritti di amministratore né altri programmi: Python, Qt, GDAL e il modello sono inclusi) e si avvia. Modello incluso: *Pharos Noise* (stime sperimentali del rumore urbano). Si disinstalla da *Impostazioni → App*. Windows può mostrare l'avviso SmartScreen perché l'installer non è firmato digitalmente: *Ulteriori informazioni → Esegui comunque*.

**Novità della 1.1.0**
- Molto più veloce, con gli stessi risultati del modello: Parigi (372.000 punti di calcolo) passa da oltre 2 ore e mezza a circa 10 minuti, Napoli a pochi minuti. Le fasi pesanti usano tutti i core del PC e a ogni esecuzione il modello controlla il calcolo su un campione di punti.
- Logo e icona definitivi.
- Messaggi della barra di avanzamento più chiari, in italiano o in inglese secondo la lingua scelta.
- Il clic sull'icona nella barra delle applicazioni riduce Sonar a icona, come le altre app di Windows.

**Risultati:** GeoPackage e File Geodatabase con stili pronti (Lden indicativo predefinito, Lnight, LAeq per fascia), una tavola PNG per output con Lden e Lnight indicativi (giorno feriale e festivo), dati di input, licenza e fonti.

---

**Install:** download `Sonar-Setup.exe`, open it, accept the license: Sonar installs for the current user (no administrator rights or other software needed: Python, Qt, GDAL and the model are included) and starts. Included model: *Pharos Noise* (experimental urban noise estimates). Uninstall from *Settings → Apps*. Windows may show a SmartScreen warning because the installer is not digitally signed: *More info → Run anyway*.

**What's new in 1.1.0**
- Much faster, with the same model results: Paris (372,000 calculation points) goes from over 2.5 hours to about 10 minutes, Naples to a few minutes. The heavy steps use all CPU cores and on every run the model checks the calculation on a sample of points.
- Final logo and icon.
- Clearer progress messages, in Italian or English depending on the selected language.
- Clicking the taskbar icon minimises Sonar, like other Windows apps.

**Results:** GeoPackage and File Geodatabase with ready styles (indicative Lden by default, Lnight, LAeq per time band), one PNG sheet per output with indicative Lden and Lnight (weekday and holiday), input data, license and sources.
