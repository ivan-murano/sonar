# Il modello acustico di Sonar

## Versione M4 (sperimentale, non predefinita)

M4 è incluso ma **non è il modello predefinito**: nelle aree rurali e aperte (es. Melfi) stima livelli più alti di M3 e appiattisce il contrasto fra strade e campagna. Le verifiche sotto usano solo sensori urbani e non vedono questo difetto.

M4 = stessa pipeline e stesse variabili della versione M3 descritta sotto, più tre novità:

1. **Addestramento su Barcellona e Dublino.** Dublino porta sensori in parchi e spazi aperti, che a Barcellona mancano. I 16 luoghi di Dublino sono divisi in 5 gruppi: ogni modello ne esclude uno, che serve da verifica.
2. **Nuove variabili** (pacchetto `noise_m4`, 58 colonne `x_*`):
   - ferrovie e tram **in superficie** entro 100/250/500 m (gallerie e binari di servizio esclusi; metro in superficie come ferrovia leggera), stazioni entro 250/500 m;
   - distanza dalla ferrovia, dalla strada principale e dall'autostrada più vicine (fino a 2 km);
   - uso del suolo OpenStreetMap (verde, acqua, industriale, residenziale, commerciale) e copertura ESA WorldCover (verde, acqua, costruito) entro 100/250/500 m;
   - attività Overture per gruppo con effetto sul rumore (vita notturna, spettacolo, sport, trasporti, parcheggi, industria, scuole, parchi, porto, emergenza, aeroporto, carburante). Overture è la fonte dei punti di interesse; da OpenStreetMap solo incroci/semafori e cantieri, per non contare due volte gli stessi luoghi.
   - Classificazione di tag OSM e categorie Overture: `configs/noise_tags_v2.json`.
3. **Nessuna variabile di popolazione** (non ci sono stime di popolazione nel modello).

| Verifica (stesso metodo per M3 e M4) | M3 | M4 |
|---|---|---|
| Barcellona, luoghi di verifica, 22–31 maggio: errore orario medio per luogo | 4,46 dB | 4,23 dB |
| Dublino, luoghi fuori campione, maggio: errore orario medio per luogo | 6,87 dB | 5,41 dB |
| Dublino: scarto medio (sovrastima) | +5,4 dB | +2,0 dB |
| Copertura della forbice 90% (Barcellona / Dublino) | 85% / 63% | 86% / 75% |
| Napoli contro mappe strategiche ufficiali 2022 (EEA, Lden, 7.292 celle): correlazione di rango | 0,44 | 0,50 |
| Napoli contro mappe ufficiali: scarto medio | +7,7 dB | +5,2 dB |

Le mappe ufficiali sono anch'esse un modello (CNOSSOS-EU, 4 m, media annua): il confronto misura l'accordo, non l'accuratezza.

---

*English summary: the Sonar acoustic model is a machine-learning model (gradient boosting) trained on the Barcelona acoustic sensor network. It describes every outdoor calculation point by its urban context within 100, 250 and 500 m (roads, buildings, points of interest, businesses open at that hour) plus the hour, day type and school calendar, and estimates hourly LAeq for a school weekday and a Sunday/holiday. Five models are combined by energy averaging into six time bands. At 30 Barcelona stations never used for training the hourly mean absolute error is 3.6 dB (correlation 0.88); at time-band level it is 3.1 dB.*

## Idea

Il rumore urbano dipende soprattutto da quanto traffico e quante attività ci sono attorno a un punto, e da come cambiano durante la giornata. Il modello impara questo legame da una città dove il rumore è misurato in continuo, Barcellona, e lo applica a qualsiasi città europea con dati aperti disponibili ovunque: OpenStreetMap, Overture Maps Places e il calendario del paese.

## Dati di addestramento

- Rete di sensori acustici della città di Barcellona: oltre 350.000 ore di misure orarie (LAeq) in decine di postazioni; addestramento su maggio 2026, controlli su febbraio e luglio.
- Contesto di ogni postazione calcolato con le stesse fonti aperte usate poi nelle altre città.
- Addestramento e verifica separati nello spazio: gruppi di postazioni entro 50 m, blocchi di 1 km, almeno 500 m fra le postazioni di addestramento e quelle di verifica; addestramento sul 1–21 maggio, verifica sul 22–31.

## Variabili (183)

| Gruppo | Contenuto |
|---|---|
| Tempo | ora del giorno, tipo di giorno (feriale, sabato, festivo) per ogni ora, giorno di scuola |
| Strade | lunghezza delle strade entro 100, 250 e 500 m: tutte, principali, a scorrimento veloce (OpenStreetMap) |
| Edifici | quota di suolo coperta da edifici entro 100, 250 e 500 m |
| Punti di interesse | conteggi per categoria entro 100, 250 e 500 m da OpenStreetMap e da Overture: ristorazione, vita notturna, istruzione, commercio, sanità, tempo libero, trasporti, uffici, altro |
| Attività aperte | per ogni ora, quante attività sono aperte entro 100, 250 e 500 m, per profilo (bar, ristoranti, negozi, uffici, scuole, sanità, locali serali…), e quota di orari osservati o stimati |

Gli orari di apertura vengono dagli orari dichiarati in OpenStreetMap quando affidabili, altrimenti da profili tipici per categoria.

## Modello

- Metodo: *gradient boosting* su alberi di decisione (scikit-learn `HistGradientBoostingRegressor`), che sceglie da solo le combinazioni di variabili che riducono l'errore fra livello misurato e stimato.
- Cinque modelli addestrati su cinque suddivisioni spaziali diverse dei dati di Barcellona. La stima finale è la loro media in energia; minimo e massimo danno la forbice.

## Dalla città alla mappa

1. Strade, edifici e punti di interesse da OpenStreetMap; attività da Overture Places.
2. Celle esagonali H3 (risoluzione 10, circa 100 m) sul comune e segmenti stradali di al massimo 50 m, spezzati agli incroci.
3. Un punto di calcolo all'aperto per ogni cella e segmento: dentro il comune, fuori dagli edifici, non sull'acqua (ESA WorldCover); per le strade presso il margine della carreggiata.
4. Contesto entro 100, 250 e 500 m di ogni punto.
5. Orari delle attività e conteggio delle attività aperte ora per ora.
6. Calendario: festività del paese e giorni di scuola.
7. Stima oraria dei cinque modelli per un giorno feriale scolastico e per una domenica o festivo; somma energetica in sei fasce: 00–06, 06–09, 09–13, 13–17, 17–21, 21–24.
8. Sonar calcola da queste fasce Lden e Lnight con la definizione della Direttiva 2002/49/CE (giorno 07–19, sera 19–23 +5 dB, notte 23–07 +10 dB).

## Accuratezza

Sulle 30 postazioni di Barcellona mai usate in nessuno dei cinque addestramenti (maggio 2026):

| Misura | Modello |
|---|---|
| Errore medio assoluto orario | 3,6 dB |
| Correlazione con le misure | 0,88 |
| Errore medio per fascia oraria | 3,1 dB |
| Distorsione media | −0,05 dB |
| Contrasto giorno (09–13) – notte (00–06) | 6,85 dB stimati, 6,83 misurati |

Febbraio e luglio danno risultati simili (3,7 dB). Gli studi recenti più vicini riportano errori quadratici medi fra 4,4 e 4,9 dB, con dati e protocolli diversi (Helbich et al. 2025, *Sustainable Cities and Society*; Haselhoff et al. 2026, *Journal of Exposure Science & Environmental Epidemiology*).

### Verifica a Dublino

Il trasferimento a una città mai vista è stato verificato a Dublino con la rete di sensori Sonitus, secondo un protocollo fissato e registrato (con impronta SHA-256) prima di vedere i dati, con un'unica esecuzione e senza alcun adattamento del modello. Periodo principale maggio 2026, 16 postazioni, 11.869 ore.

| Misura | Modello | Riferimento solo ora del giorno |
|---|---|---|
| Correlazione di rango fra luoghi (Spearman) | 0,82 (IC 90% 0,58–0,92) | — |
| Errore medio sui livelli dei luoghi, al netto dello scarto di città | 4,2 dB | 5,5 dB |
| Errore orario medio (MAE) | 6,9 dB | 10,5 dB |
| Scarto medio (stimato − misurato) | +5,4 dB | +9,4 dB |
| Correlazione del profilo giornaliero feriale (mediana fra luoghi) | 0,88 | 0,84 |

Esito del protocollo: **parziale**. Superati C1 (ordinamento dei luoghi) e C2 (livelli dei luoghi meglio del riferimento); non superati C3 (errore orario entro 6 dB) e C4 (scarto medio entro 3 dB). In sintesi: l'ordinamento spaziale e il ritmo della giornata si trasferiscono; i livelli assoluti richiedono una taratura locale. Con cinque sensori locali (scenario adattato, separato dal precedente) lo scarto medio si annulla e l'errore orario medio scende a 5,8 dB (intervallo 5–95%: 4,4–7,1 dB). Febbraio e luglio danno risultati coerenti (correlazione di rango 0,78 in entrambi).

## Bibliografia essenziale

- EEA (2025, corretto 2026). *Environmental noise in Europe 2025*. European Environment Agency.
- Razai et al. (2025). *BMJ* 391, bmj-2024-081193.
- Gonzato et al. (2026). Rumore dei trasporti ed esiti cardiovascolari, revisione sistematica e meta-regressione. *J. Expo. Sci. Environ. Epidemiol.*
- Helbich M. et al. (2025). *Sustainable Cities and Society*, doi:10.1016/j.scs.2025.106169.
- Haselhoff T. et al. (2026). *J. Expo. Sci. Environ. Epidemiol.*, nature.com/articles/s41370-026-00855-w.
- Wu e Wang (2025). *Computers, Environment and Urban Systems*, doi:10.1016/j.compenvurbsys.2025.102327.
- WHO Regional Office for Europe (2018). *Environmental Noise Guidelines for the European Region*.

Il collegamento fra modello e software è descritto in [MODEL_CONTRACT.md](MODEL_CONTRACT.md).
