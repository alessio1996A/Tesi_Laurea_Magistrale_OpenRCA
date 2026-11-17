# RQ2: dettaglio delle spiegazioni (testo libero del passo D), griglia C1-C5, 17 novembre 2026

Griglia e regole: `RQ2_GRIGLIA_SPIEGAZIONI_PROPOSTA_2026-11-17.md` (registro righe 41-42). Materiale: 60 testi
(4 incidenti x 3 modelli x 5 harness), da `testo_libero_D_C.csv`. Punteggi assegnati da Claude, testo per testo,
applicando le definizioni alla lettera; punteggi per testo e chiave del campione cieco committati **dopo** la rilettura
di Alessio (accordo da riportare).

## Avvertenze sul materiale

- Il passo D di **cloudbed-2_q026** e' un compito di solo orario (task_1): 10 testi su 15 sono vuoti per costruzione
  del compito, non per scarsa spiegazione. Si riportano i risultati con e senza q026.
- C4 si valuta solo sul testo; l'orario nei campi strutturati (`datetime`) non conta qui.
- Il "dettaglio" dipende in parte dalla lunghezza del testo: la griglia non separa dettaglio e verbosita'.

## Punteggio medio di dettaglio (0-5)

| Modello | Tutti i 4 incidenti (n=20) | Senza q026 (n=15) |
|---|---:|---:|
| Sonnet | 2,70 | 3,40 |
| Haiku | 2,35 | 3,13 |
| Gemini | 1,35 | 1,47 |

| Harness (n=12, 3 modelli) | Media |
|---|---:|
| A0 | 2,00 |
| A1 | 2,58 |
| A1_8R | 2,08 |
| A1_8R_Planning | 1,75 |
| A1_PAVE | 2,25 |

Per criterio, testi con punteggio 1 su 20 per modello (C1, C2, C3, C4, C5): Gemini 14, 12, 1, 0, 0; Sonnet 16, 15, 12, 7, 4;
Haiku 15, 15, 14, 1, 2.

## Lettura (descrittiva, n piccolo, un solo lettore)

1. I modelli Claude scrivono spiegazioni con piu' osservazioni e inferenze (C3) di Gemini, che per lo piu' restituisce
   etichette brevi; C4 (quando) e C5 (incertezza) sono rari per tutti e quasi solo di Sonnet.
2. Per harness non c'e' un andamento ordinato: A1 e' il piu' alto (2,58) ma dovuto in gran parte a Sonnet (4,25), e
   A1_8R_Planning e' il piu' basso.
3. Le differenze di lunghezza e di formato di risposta possono spiegare parte delle differenze tra modelli: non e' un
   confronto di "capacita' di capire".

## Limiti

Il lettore e' un modello della famiglia Claude: potrebbe favorire il proprio stile (da qui la rilettura di Alessio su
12 testi). Alcune decisioni su C3 sono di confine (osservazione senza inferenza = 0). La passata 2 (correttezza rispetto
alla classe vera) non e' ancora fatta. Nessun test inferenziale.
