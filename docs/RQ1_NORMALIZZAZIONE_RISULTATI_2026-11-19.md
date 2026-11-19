# RQ1 — Risultati di EVALUATION20 normalizzati rispetto ad A0

**Data:** 19 novembre 2026. **Stato:** eseguito, sola lettura, nessun dato congelato modificato.
**Perimetro:** analisi descrittiva post hoc dei 300 tentativi di EVALUATION20 (20 incidenti Market ×
3 modelli × 5 varianti). Non sostituisce il confronto primario preregistrato (sezione 6).

## 1. Che cosa è stato fatto e perché

- **Richiesta del relatore** (colloquio del 19 novembre, da trascrizione): presentare i risultati
  normalizzati, con il valore più basso come riferimento e gli altri come multipli. *Interpretazione di
  Alessio, da lui confermata:* il riferimento è A0 dello stesso modello.
- **Riferimento.** Per l'accuratezza A0 è anche la media più bassa in tutti e tre i modelli
  (Gemini 0,079; Sonnet 0,117; Haiku 0,142). Per token e tempo A0 **non** è il più basso (per Sonnet e
  Haiku è il più alto): si è tenuto A0 per coerenza, quindi un rapporto minore di 1 indica un
  risparmio rispetto a A0. Non si confrontano modelli o provider diversi: i token sono contati in modo
  diverso da provider diversi.
- **I dati originali restano intatti e affiancati.** In ogni riga delle tabelle compaiono la media
  assoluta e il numero di run (n) accanto al multiplo; i multipli si verificano dividendo le medie
  riportate. Il modulo `src/evaluation/rq1_normalization.py` apre i file congelati solo in lettura
  (un test verifica che gli hash di tutti i file preesistenti restano identici) e scrive due file
  nuovi, in modalità create-only.
- **Popolazione.** Le 295 run con punteggio ufficiale congelato (stato `complete`, conteggio dei token
  completo). Le 5 run senza punteggio (errori 503 di Gemini, mai riprovati) sono fuori da punteggi,
  token e tempi. Le medie di cella sono sugli incidenti con punteggio: l'n varia da 18 a 20 per Gemini.
- **Intervalli.** Bootstrap sugli incidenti, 10.000 estrazioni, seme 20261119, percentili 2,5 e 97,5.
  Non corretti per confronti multipli.
- **Regola fissata prima di leggere i numeri.** Se le 15 medie dei punteggi già riportate non fossero
  state riprodotte, il comando si sarebbe fermato e nessun numero sarebbe stato usabile (stessa regola
  della stratificazione, registro riga 37).

## 2. Controlli superati (dal report)

- Le 15 medie e i 15 n già riportati sono riprodotti (`reproduction_of_reported_means.all_match` = vero).
- Run: 300 totali, 295 con punteggio, 5 senza; 20 incidenti.
- Discordanze di hash dei risultati sorgente: 0. Chiamate ai modelli: 0. Ground truth non aperta.
- Il piano usato ha SHA-256 `d390d7acd3db6931c48a64bcd35757ebadf7a7dbdb12b718c1154b45e8757342`
  (verificato dal modulo contro il report di scoring congelato).

## 3. Tabelle

Generate dal report con `--tables-from` e incollate qui **senza modifiche** (dal file prodotto
dall'esecuzione di Alessio, 19 novembre, 10:40). Gli arrotondamenti sono quelli di Python sul valore
binario: nei casi esattamente a metà (per esempio 0,0875) il terzo decimale può risultare inferiore di
una unità rispetto all'arrotondamento convenzionale; non cambia nessuna lettura.

Fonte: report `rq1_normalization_v1`, protocollo `openrca_harness_evaluation20_cross_model_v1`. Riferimento: A0 dello stesso modello. Run con punteggio: 295 su 300 (20 incidenti). Intervalli al 95% per ricampionamento degli incidenti (10000 estrazioni, seme 20261119), non corretti per confronti multipli.

**Tabella 1. Punteggio medio (scala 0-1)**

| Modello | Variante | n | Media | x A0 | Differenza da A0 (punti) | IC95% della differenza | IC95% di x A0 | IC della differenza esclude 0 |
|---|---|---:|---:|---:|---:|---|---|---|
| gemini | A0 | 19 | 0,079 | rif. | rif. | n.a. | n.a. | n.a. |
| gemini | A1 | 19 | 0,167 | 2,11 | +0,088 | [-0,026; +0,211] | [0,78; 8,78] | no |
| gemini | A1_8R | 18 | 0,116 | 1,46 | +0,037 | [-0,062; +0,140] | [0,42; 5,88] | no |
| gemini | A1_8R_Planning | 20 | 0,221 | 2,79 | +0,142 | [-0,027; +0,320] | [0,78; 14,32] | no |
| gemini | A1_PAVE | 19 | 0,215 | 2,72 | +0,136 | [-0,022; +0,294] | [0,83; 13,18] | no |
| sonnet | A0 | 20 | 0,117 | rif. | rif. | n.a. | n.a. | n.a. |
| sonnet | A1 | 20 | 0,396 | 3,40 | +0,280 | [+0,100; +0,467] | [1,48; 15,14] | si' |
| sonnet | A1_8R | 20 | 0,433 | 3,72 | +0,317 | [+0,134; +0,509] | [1,75; 16,50] | si' |
| sonnet | A1_8R_Planning | 20 | 0,366 | 3,15 | +0,250 | [+0,075; +0,450] | [1,38; 14,00] | si' |
| sonnet | A1_PAVE | 20 | 0,504 | 4,33 | +0,388 | [+0,200; +0,588] | [2,04; 19,50] | si' |
| haiku | A0 | 20 | 0,142 | rif. | rif. | n.a. | n.a. | n.a. |
| haiku | A1 | 20 | 0,229 | 1,62 | +0,087 | [-0,100; +0,275] | [0,50; 5,91] | no |
| haiku | A1_8R | 20 | 0,275 | 1,94 | +0,134 | [-0,091; +0,350] | [0,62; 8,24] | no |
| haiku | A1_8R_Planning | 20 | 0,241 | 1,71 | +0,100 | [-0,117; +0,317] | [0,47; 7,33] | no |
| haiku | A1_PAVE | 20 | 0,321 | 2,27 | +0,179 | [-0,066; +0,413] | [0,73; 9,84] | no |

**Tabella 2. Token totali medi per run**

| Modello | Variante | n | Media | x A0 | Differenza da A0 (token) | IC95% della differenza | IC95% di x A0 | IC della differenza esclude 0 |
|---|---|---:|---:|---:|---:|---|---|---|
| gemini | A0 | 19 | 34864 | rif. | rif. | n.a. | n.a. | n.a. |
| gemini | A1 | 19 | 42839 | 1,23 | +7975 | [+115; +16159] | [1,00; 1,48] | si' |
| gemini | A1_8R | 18 | 53731 | 1,54 | +18867 | [+10143; +28693] | [1,28; 1,85] | si' |
| gemini | A1_8R_Planning | 20 | 38530 | 1,11 | +3666 | [-687; +8199] | [0,98; 1,25] | no |
| gemini | A1_PAVE | 19 | 37438 | 1,07 | +2574 | [-1979; +7579] | [0,95; 1,22] | no |
| sonnet | A0 | 20 | 122215 | rif. | rif. | n.a. | n.a. | n.a. |
| sonnet | A1 | 20 | 94429 | 0,77 | -27786 | [-56596; -196] | [0,58; 1,00] | si' |
| sonnet | A1_8R | 20 | 93957 | 0,77 | -28258 | [-56399; -506] | [0,58; 1,00] | si' |
| sonnet | A1_8R_Planning | 20 | 67787 | 0,55 | -54429 | [-78814; -29700] | [0,45; 0,70] | si' |
| sonnet | A1_PAVE | 20 | 73199 | 0,60 | -49017 | [-73111; -24850] | [0,49; 0,75] | si' |
| haiku | A0 | 20 | 132416 | rif. | rif. | n.a. | n.a. | n.a. |
| haiku | A1 | 20 | 80048 | 0,60 | -52368 | [-70178; -33607] | [0,49; 0,73] | si' |
| haiku | A1_8R | 20 | 72115 | 0,54 | -60301 | [-82288; -37655] | [0,41; 0,70] | si' |
| haiku | A1_8R_Planning | 20 | 84340 | 0,64 | -48076 | [-68584; -27603] | [0,53; 0,77] | si' |
| haiku | A1_PAVE | 20 | 76851 | 0,58 | -55564 | [-73023; -37093] | [0,48; 0,69] | si' |

**Tabella 3. Tempo end-to-end medio per run**

| Modello | Variante | n | Media | x A0 | Differenza da A0 (secondi) | IC95% della differenza | IC95% di x A0 | IC della differenza esclude 0 |
|---|---|---:|---:|---:|---:|---|---|---|
| gemini | A0 | 19 | 83,8 | rif. | rif. | n.a. | n.a. | n.a. |
| gemini | A1 | 19 | 77,9 | 0,93 | -6,0 | [-27,0; +16,5] | [0,70; 1,22] | no |
| gemini | A1_8R | 18 | 84,1 | 1,00 | +0,3 | [-17,8; +17,3] | [0,81; 1,24] | no |
| gemini | A1_8R_Planning | 20 | 69,1 | 0,82 | -14,7 | [-32,7; +2,0] | [0,65; 1,03] | no |
| gemini | A1_PAVE | 19 | 64,6 | 0,77 | -19,2 | [-35,3; -2,2] | [0,63; 0,97] | si' |
| sonnet | A0 | 20 | 158,6 | rif. | rif. | n.a. | n.a. | n.a. |
| sonnet | A1 | 20 | 128,2 | 0,81 | -30,3 | [-75,7; +14,3] | [0,57; 1,10] | no |
| sonnet | A1_8R | 20 | 125,9 | 0,79 | -32,7 | [-75,8; +9,3] | [0,55; 1,06] | no |
| sonnet | A1_8R_Planning | 20 | 98,1 | 0,62 | -60,5 | [-100,0; -26,6] | [0,45; 0,81] | si' |
| sonnet | A1_PAVE | 20 | 110,3 | 0,70 | -48,2 | [-84,9; -15,2] | [0,53; 0,89] | si' |
| haiku | A0 | 20 | 216,5 | rif. | rif. | n.a. | n.a. | n.a. |
| haiku | A1 | 20 | 122,8 | 0,57 | -93,7 | [-127,5; -62,8] | [0,44; 0,69] | si' |
| haiku | A1_8R | 20 | 97,7 | 0,45 | -118,8 | [-163,5; -76,1] | [0,31; 0,62] | si' |
| haiku | A1_8R_Planning | 20 | 112,5 | 0,52 | -104,0 | [-145,9; -65,5] | [0,40; 0,66] | si' |
| haiku | A1_PAVE | 20 | 95,0 | 0,44 | -121,5 | [-155,8; -91,3] | [0,34; 0,54] | si' |

Nota sul punteggio: nei ricampionamenti in cui la media di A0 e' zero il rapporto non e' definito e quei ricampionamenti sono esclusi dall'intervallo del rapporto (per A1: gemini 121 su 10000, sonnet 100 su 10000, haiku 22 su 10000). Il rapporto con A0 basso ingigantisce le differenze piccole: l'intervallo della differenza e' il riferimento piu' stabile.

**Tabella 4. Variazione A1_8R -> A1_8R_Planning: ricalcolo e relazione del 9 novembre (media, tempo end-to-end)**

| Modello | Token ricalcolati | Token relazione | Tempo ricalcolato | Tempo relazione |
|---|---:|---:|---:|---:|
| sonnet | -27,9% | -27,9% | -22,1% | -22,1% |
| haiku | +17,0% | +17,0% | +15,2% | +15,2% |
| gemini | -28,3% | -27,8% | -17,8% | -17,2% |

## 4. Che cosa dicono i dati

Solo quanto osservato nelle tabelle e nel report.

**Accuratezza (Tabella 1)**
- La stima puntuale del multiplo rispetto ad A0 è maggiore di 1 in tutte le 12 combinazioni
  modello × variante: da 1,46 (Gemini, A1_8R) a 4,33 (Sonnet, A1_PAVE).
- L'intervallo della differenza da A0 esclude lo zero in **tutte e 4** le varianti di Sonnet e in
  **nessuna** delle 8 di Haiku e Gemini. Per Haiku e Gemini i multipli sono quindi stime puntuali non
  distinguibili da un effetto nullo con 20 incidenti.
- La mediana del punteggio è 0 per A0 in tutti e tre i modelli e resta 0 in tutte le varianti di
  Haiku e Gemini; per Sonnet vale 0,5 (A1), 0,375 (A1_8R), 0,165 (Planning), 0,5 (PAVE)
  (`summaries.score.*.median` del report). Le medie di Haiku e Gemini sono quindi trainate da una
  minoranza di incidenti.
- Gli intervalli dei multipli sono molto larghi (fino a 19,50 per Sonnet con A1_PAVE) perché la media
  di A0 è bassa. In alcuni ricampionamenti la media di A0 è zero e il rapporto non è definito: sono
  esclusi dall'intervallo del rapporto (per A1: 121, 100 e 22 su 10.000 per Gemini, Sonnet, Haiku),
  quindi il limite superiore potrebbe essere sottostimato. L'intervallo della differenza è più
  stabile e va riportato accanto al multiplo.

**Token (Tabella 2)**
- Con Sonnet e Haiku tutte le 8 varianti con harness usano meno token di A0 (da 0,54 a 0,77 volte);
  l'intervallo della differenza esclude lo zero in tutte. Per Sonnet con A1 e A1_8R il limite superiore
  del rapporto è al confine (0,998 e 0,995 nel report).
- Con Gemini tutte e 4 le varianti ne usano di più (da 1,07 a 1,54 volte); l'intervallo della
  differenza esclude lo zero solo per A1 e A1_8R.

**Tempo end-to-end (Tabella 3)**
- Haiku: tutte e 4 le varianti sono più veloci (0,44–0,57 volte), intervalli che escludono lo zero.
- Sonnet: Planning (0,62) e PAVE (0,70) escludono lo zero; A1 (0,81) e A1_8R (0,79) no.
- Gemini: solo PAVE (0,77; differenza −19,2 s, IC [−35,3; −2,2]) esclude lo zero.

## 5. Che cosa non si può dire

- Non «l'harness triplica l'accuratezza» in generale: 3,40 volte (A1) vale per Sonnet; per Haiku e
  Gemini nessun multiplo è distinguibile da un effetto nullo.
- Nessun confronto tra modelli: ogni rapporto è rispetto ad A0 dello stesso modello.
- Nessuna generalizzazione: 20 incidenti, un solo sistema (Market), una sola esecuzione per cella,
  analisi post hoc.
- L'ordine tra varianti (per esempio PAVE contro Planning) non è oggetto di questa normalizzazione; le
  ablazioni sono non monotone (consolidamento, sez. 3.1).

## 6. Rapporto con la relazione del 9 novembre

- **Confronto primario preregistrato:** A1 − A0 **appaiato** entro modello (consolidamento sez. 3.1).
  Sonnet 20 coppie, +0,2795 [+0,1000; +0,4715]; Haiku 20 coppie, +0,0875 [−0,1000; +0,2750];
  Gemini **18 coppie**, +0,0928 [−0,0278; +0,2228]. Resta la fonte del confronto primario.
- **Differenze con questa analisi.** Sonnet e Haiku: stessa differenza puntuale (+0,2795; +0,0875).
  Intervalli: Haiku identico; Sonnet [+0,100; +0,467] contro [+0,1000; +0,4715]. Gemini: +0,088
  [−0,026; +0,211] qui, calcolato su 19 e 19 incidenti con punteggio non necessariamente gli stessi,
  contro +0,0928 della relazione su 18 coppie. La spiegazione più probabile è la diversa popolazione
  (incidenti comuni alle due varianti contro incidenti disponibili in ciascuna), coerente con le 18
  coppie del consolidamento; **non è stata verificata con un ricalcolo**.
- **Efficienza A1_8R → Planning (Tabella 4).** Sonnet (−27,9% token, −22,1% tempo) e Haiku (+17,0%,
  +15,2%) sono riprodotti esattamente con media e tempo end-to-end. Gemini no: −28,3% e −17,8% contro
  −27,8% e −17,2%. Le definizioni con mediana o con durata senza preprocessing non coincidono con la
  relazione per nessun modello (`efficiency_vs_report_of_9_nov` del report). Stessa ipotesi sulla
  popolazione, non verificata.
- **Come si usa nella tesi.** Il confronto primario A1 − A0 si cita dalla relazione (appaiato); le
  tabelle normalizzate si presentano come analisi descrittiva con le proprie definizioni e l'n per
  cella; dove i due insiemi di numeri convivono (Gemini) la differenza si dichiara.

## 7. Limiti

- Analisi post hoc di dati congelati; una esecuzione per cella: la variabilità tra esecuzioni non è
  misurata e i 300 tentativi non sono indipendenti.
- Intervalli non corretti per confronti multipli.
- Rapporti con A0 basso ingigantiscono differenze piccole (Gemini A0 = 0,079).
- Gemini ha 5 run senza punteggio: n diverso da 20 in alcune celle.
- Token confrontabili solo entro lo stesso modello.
- Il codice è scritto da Claude Sonnet 5.5, che è anche uno dei tre modelli valutati: conflitto di
  interesse da elencare tra le minacce alla validità (registro, limiti dichiarati).

## 8. Seguito

1. Verificare l'ipotesi sulla popolazione per Gemini ricalcolando differenze e variazioni sugli
   incidenti comuni (comando di sola lettura da aggiungere), prima di scrivere il capitolo RQ1.
2. Figura per il capitolo RQ1: punteggi assoluti con multipli e intervalli; da fare quando si scrive il
   capitolo.
3. Il relatore ha chiesto di normalizzare «in generale»: applicare lo stesso criterio ai risultati di
   RQ2 solo dove il riferimento è diverso da zero (per esempio i punteggi di D sono zero: restano i
   valori assoluti).

## 9. Fonti

| Voce | Dove |
|---|---|
| Report completo | Drive, `Tesi_OpenRCA/data/rq1_normalization_v1/normalization.json`; SHA-256 stampato dal comando `27f74fae1f14399bb9df8058d592b9f0fdfda257bf12c282734cadc261a2a983` |
| Tabelle | Drive, `Tesi_OpenRCA/data/rq1_normalization_v1/normalization_tables.md` (copiate qui senza modifiche) |
| Codice e test | `src/evaluation/rq1_normalization.py`, `src/tests/test_rq1_normalization.py` (commit `73497e6`, `bfb3863`; 27 test) |
| Punteggi congelati sorgente | `openrca_harness_evaluation20_cross_model_v1_official_raw_scoring_v1.json` (Drive, `data/…/evaluation20`) |
| Confronto primario e tabella delle medie | `docs/CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md`, sez. 3.1 (relazione del 9 novembre) |
| Richiesta del relatore | `docs/CONTESTO_SCRITTURA_TESI_GPT_2026-11-19.md`, sez. 2 |
