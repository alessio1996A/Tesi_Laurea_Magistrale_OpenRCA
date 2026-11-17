# RQ2: lettura dei record K e dei motivi di astensione (17 novembre 2026)

Sola lettura, nessuna nuova chiamata a modelli. Materiale: `k_testi_v2.csv` (Drive, `data/rq2_k_testo_v1/`, 140715 byte),
esportato in Colab dai 60 record K di `data/rq2_v5_format_fair_v1/records`. Un primo file `k_testi.csv` (vuoto, 0 righe)
nasce da un percorso sbagliato e non e' stato cancellato. Griglia K1-K5 congelata in
`RQ2_GRIGLIA_SPIEGAZIONI_PROPOSTA_2026-11-17.md` (registro riga 41); non modificata.

## Esiti dei 60 K

- 8 candidate, 52 astensioni (`insufficient_evidence`). Delle 52, 3 hanno stato di record `INVALID_OUTPUT` pur con JSON
  leggibile: 52 - 3 = 49 astensioni valide, che e' il numero riportato in precedenza.
- Candidate per modello: Gemini 4, Sonnet 3, Haiku 1. Astensioni: Haiku 19, Sonnet 17, Gemini 16.

## Motivi di astensione (ricerca per parole chiave nei campi `abstain_when` e `limitations`; conteggio approssimato)

| Motivo citato | Totale su 52 | Haiku (19) | Sonnet (17) | Gemini (16) |
|---|---:|---:|---:|---:|
| soglia o baseline non supportata dai dati | 49 | 19 | 17 | 13 |
| dati mancanti, assenti o troncati | 46 | 19 | 17 | 10 |
| diagnosi non verificata (`diagnosis_is_gt_verified=false`) | 36 | 19 | 16 | 1 |
| unita' non verificate (`units_verified=false`) | 28 | 16 | 12 | 0 |
| finestra di guasto non validata | 6 | 4 | 2 | 0 |

Lettura: le astensioni di Haiku e Sonnet citano quasi sempre che il pacchetto di evidenze dichiara le unita' non
verificate e la diagnosi non verificata, e che quindi nessuna soglia e' giustificabile. Gemini si astiene con
motivazioni piu' brevi, senza citare le unita'. **Ipotesi (non testata):** la richiesta di una regola con soglia
quantitativa, data insieme a evidenze marcate come "unita' non verificate", spinge i modelli piu' prudenti ad
astenersi. Togliere quella marcatura richiederebbe un nuovo esperimento: non fatto.

## Le 8 candidate con la griglia K (0/1)

| # | Caso | Modello / harness | Regola (sintesi) | K1 | K2 | K3 | K4 | K5 | Tot |
|---|---|---|---|---|---|---|---|---|---:|
| 1 | cloudbed-1_q032 | gemini A0 | latenza max checkoutservice-grpc > 1000 ms su 1800 s | 1 | 1 | 1 | 1 | 1 | 5 |
| 2 | cloudbed-1_q032 | haiku A0 | durata massima span cartservice-0 >= 1000 ms | 1 | 1 | 1 | 1 | 0 | 4 |
| 3 | cloudbed-2_q045 | sonnet A1 | errori driver MySQL nei log per pod >= 1 su 60 s | 1 | 1 | 1 | 1 | 1 | 5 |
| 4 | cloudbed-2_q045 | gemini A1_8R_Planning | errori applicativi adservice > 0 su 60 s | 1 | 1 | 1 | 1 | 1 | 5 |
| 5 | cloudbed-1_q050 | sonnet A0 | throttling CFS del container > 0 su 1800 s | 1 | 1 | 1 | 1 | 1 | 5 |
| 6 | cloudbed-1_q032 | sonnet A1_8R_Planning | avanzamento di `container_start_time_seconds` (riavvio) su 600 s | 1 | 1 | 1 | 1 | 1 | 5 |
| 7 | cloudbed-2_q045 | gemini A0 | mrt_max productcatalogservice > 10000 ms su 60 s | 1 | 1 | 1 | 1 | 0 | 4 |
| 8 | cloudbed-2_q026 | gemini A1_8R | iowait nodo >= 10% su 60 s | 1 | 1 | 1 | 1 | 1 | 5 |

K5 = 0 per #2 (clausole di astensione non operative: "componenti non correlati dominano senza separazione") e per
#7 (lo pseudocodice aggiunge una condizione sui log che non e' nelle condizioni strutturate).

**Limite dello strumento, dichiarato:** lo schema di output impone metrica, operatore, soglia, unita', aggregazione e
finestra, quindi K1-K4 valgono 1 per costruzione e non discriminano. L'unico criterio che varia e' K5, giudicato da un
modello della famiglia Claude (limite gia' dichiarato). Medie K5/totale per modello: Gemini 4,75 (4 candidate),
Sonnet 5,0 (3), Haiku 4,0 (1): con questi numeri non si confrontano i modelli.

**Osservazione non punteggiata, da verificare nei campi `limitations`:** le tre soglie di Gemini (1000 ms, 10000 ms, 10%)
non risultano agganciate a una baseline osservata nei campi letti; le candidate dei modelli Claude usano per lo piu'
soglie di presenza dell'evento (>0, >=1) con condizioni di astensione esplicite.

## Cosa NON si afferma

Nessuna valutazione di correttezza rispetto alla classe vera (passata 2, non ancora fatta). Nessun confronto
statistico tra modelli. Nessuna conclusione sul contributo dell'harness (A0 ha 4 candidate su 12 K, come gia' noto).
