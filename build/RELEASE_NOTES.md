## Sonar 1.3.0

**Novità: modello acustico M4.** Il modello ora è addestrato sui sensori di Barcellona e di Dublino e usa anche ferrovie e tram in superficie, stazioni, distanze da ferrovie, strade principali e autostrade, uso del suolo (OpenStreetMap, ESA WorldCover) e le attività Overture per tipo. Sovrastima molto minore negli spazi aperti e nei parchi.

| Verifica (stesso metodo) | M3 (1.2.1) | M4 (1.3.0) |
|---|---|---|
| Barcellona, postazioni di verifica: errore orario medio per luogo | 4,46 dB | 4,23 dB |
| Dublino, postazioni escluse dall'addestramento: errore orario medio | 6,87 dB | 5,41 dB |
| Dublino: sovrastima media | +5,4 dB | +2,0 dB |
| Napoli contro le mappe strategiche ufficiali EEA 2022 (Lden): correlazione | 0,44 | 0,50 |

Il modello M3 resta incluso (non predefinito). Tutto il resto come nella 1.2.1.

**Novelty: M4 acoustic model**, trained on Barcelona and Dublin sensors, adding surface railways and trams, stations, distances to railways/main roads/motorways, land use (OpenStreetMap, ESA WorldCover) and Overture places by type. Much less overestimation in open spaces and parks. Barcelona 4.46→4.23 dB, Dublin (out of sample) 6.87→5.41 dB, Dublin bias +5.4→+2.0 dB, Napoli vs official EEA 2022 maps rank correlation 0.44→0.50. M3 remains included (not default).

---

## Sonar 1.2.1

**Installazione:** scaricare `Sonar-Setup.exe`, aprirlo, accettare la licenza: Sonar si installa per l'utente corrente (non servono diritti di amministratore né altri programmi: Python, Qt, GDAL e il modello sono inclusi) e si avvia. Il modello acustico è incluso. Si disinstalla da *Impostazioni → App*. Windows può mostrare l'avviso SmartScreen perché l'installer non è firmato digitalmente: *Ulteriori informazioni → Esegui comunque*.

**In breve:** si scrive il nome della città e Sonar consegna la mappa del rumore pronta per QGIS e ArcGIS: livello sonoro stimato ogni 100 m e su ogni strada, in sei fasce orarie per un giorno feriale e un festivo, con Lden e Lnight. Parigi in circa dieci minuti, città medie in pochi minuti, tutto sul proprio PC.

**Popolazione esposta.** Sonar attribuisce i residenti (JRC GHS-POP 2020, griglia di 100 m) alle celle della mappa e consegna in `Risultati/Popolazione esposta` un foglio Excel e una tavola A4 con i residenti per classe di Lden e Lnight della Direttiva 2002/49/CE, giorno feriale e festivo. I layer delle celle hanno il campo `residenti`.

**Accuratezza:** su 30 postazioni di Barcellona mai usate per l'addestramento l'errore orario medio è di 3,6 dB, con correlazione 0,88. A Dublino, senza alcuna taratura locale, il modello ordina le 16 postazioni Sonitus con correlazione di rango 0,82 (dettagli nel README).

**Risultati:** GeoPackage e File Geodatabase con stili pronti (Lden predefinito, Lnight, LAeq per fascia), una tavola PNG per output con una sola scala di colori per Lden e Lnight, popolazione esposta, dati di input, licenza e fonti.

---

**Install:** download `Sonar-Setup.exe`, open it, accept the license: Sonar installs for the current user (no administrator rights or other software needed: Python, Qt, GDAL and the model are included) and starts. The acoustic model is included. Uninstall from *Settings → Apps*. Windows may show a SmartScreen warning because the installer is not digitally signed: *More info → Run anyway*.

**In short:** type a city name and Sonar delivers its noise map ready for QGIS and ArcGIS: estimated sound level every 100 m and on every road, in six time bands for a weekday and a holiday, with Lden and Lnight. Paris in about ten minutes, mid-size cities in a few minutes, all on your own PC.

**Population exposure.** Sonar assigns residents (JRC GHS-POP 2020, 100 m grid) to the map cells and delivers, in `Results/Population exposure`, a spreadsheet and an A4 sheet with residents by Lden and Lnight class of Directive 2002/49/EC, weekday and holiday. The cell layers carry the `residenti` (residents) field.

**Accuracy:** at 30 Barcelona stations never used in training the mean hourly error is 3.6 dB, with a correlation of 0.88. In Dublin, with no local calibration, the model ranks the 16 Sonitus stations with a rank correlation of 0.82 (details in the README).

**Results:** GeoPackage and File Geodatabase with ready styles (Lden by default, Lnight, LAeq per time band), one PNG sheet per output with one colour scale for Lden and Lnight, population exposure, input data, license and sources.
