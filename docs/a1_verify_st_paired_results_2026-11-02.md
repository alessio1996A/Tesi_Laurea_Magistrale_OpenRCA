# Secondo confronto sperimentale: A1_VERIFY vs A1_VERIFY_ST (2 novembre 2026)

## Inquadramento e stato

Esperimento **completato, congelato e valutato** su otto incidenti *development* OpenRCA 1.0 Market, selezionati con coorte preregistrata e finestre non sovrapposte. Le 16 diagnosi (una per variante e caso) sono state prodotte con `gemini-3.5-flash-lite` e conservate su Google Drive. Tutte le run hanno superato l'audit strutturale; lo scoring ufficiale è stato eseguito **solo dopo il congelamento degli output**.

**Attenzione:** questa è una prova esplorativa di fattibilità, non una conferma su evaluation o OOD holdout, e non dimostra superiorità causale o significatività statistica.

## Versione del codice e variabile sperimentale

- **Codice sperimentale esatto:** `138fb523efec4a665a2424ab2faedb698f10562e` sul branch `feature/a1-verify-st-v1`.
- **Branch per il relatore:** `presentation/relatore-2026-11-02`. Può contenere aggiornamenti documentali ulteriori rispetto al codice sperimentale: per riprodurre le run usare **il commit esatto**, non il branch HEAD.
- **A1_VERIFY:** evidenze unificate, otto regole deterministiche R01/R02/R06–R11, massimo 4 round esplorativi LLM + massimo 2 round del planner, finalizzazione LLM.
- **A1_VERIFY_ST:** identico assetto **più** un contesto deterministico strutturale-temporale, derivato dalle evidenze, allegato **solo alla finalizzazione**. Non modifica planner, regole, tool, budget o prompt di base.
- Entrambe: `max_tool_rounds=6`, `max_verification_checks=2`, `output_contract_mode=legacy`, cinque tool di telemetria.
- Il numero di verifiche concretamente eseguite può essere 0, 1 o 2. I due agenti possono esplorare diversamente a causa della variabilità LLM.

## Provenienza degli artefatti (Google Drive / Tesi_OpenRCA)

| Artefatto | Percorso / SHA-256 |
|---|---|
| Piano preregistrato | `data/protocols/a1_verify_st_paired_development_v1_cohort_v1.json` |
| SHA-256 piano | `b93d38ce4dcda942ce6b3c01cd5af80ae7f957857025fc73afca745ba11e6166` |
| Risultati e marcatori (8 coppie) | `data/results/paired/a1_verify_st_paired_development_v1/` |
| Manifest di congelamento delle 16 predizioni | `data/protocols/a1_verify_st_paired_development_v1_predictions_frozen_v1.json` |
| SHA-256 manifest di congelamento | `43e646792685b1cde03052cadc2c8a82749d058a4e04ee0b01f607a7384fd104` |
| Scoring ufficiale, separato dalle predizioni | `data/results/a1_verify_st_paired_development_v1_official_scoring_v1.json` |
| SHA-256 scoring | `26f10169e379f9a8ceabcd83923ae7daa72ca90f705e021d77e6eb5772027f45` |

Hash dei dati GT-free, verificati prima delle API:
- `split_market_v1.csv`: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`
- `benchmark_inputs_market.csv`: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`

La ground truth è stata consultata **soltanto nel notebook separato di scoring**, dopo il freeze. I file originali su Drive non vanno modificati, rigenerati o sostituiti.

## Risultati ufficiali aggregati

| Misura | A1_VERIFY | A1_VERIFY_ST |
|---|---:|---:|
| Score medio OpenRCA | 0,2288 | **0,2913** |
| Score esattamente 1 | 0/8 | 1/8 |
| Output conformi secondo il parser legacy | 7/8 | 8/8 |
| Token totali (uso completo) | 318.154 | 349.266 |
| Durata end-to-end totale | 536,519 s | 520,649 s |

Differenza media di score appaiata **+0,0625**, consumo totale token **+9,78%** per ST, tempo totale **−2,96%** per ST. Queste differenze non sono prova di un vantaggio ripetibile.

### Analisi appaiata per caso

| Caso | Score A1_VERIFY | Score A1_VERIFY_ST | Delta ST – VERIFY |
|---|---:|---:|---:|
| cloudbed-1_q016 | 0,00 | 0,00 | 0,00 |
| cloudbed-1_q036 | 0,50 | 0,00 | −0,50 |
| cloudbed-1_q043 | 0,50 | 0,50 | 0,00 |
| cloudbed-1_q065 | 0,50 | 0,50 | 0,00 |
| cloudbed-2_q053 | 0,00 | 1,00 | +1,00 |
| cloudbed-2_q055 | 0,00 | 0,00 | 0,00 |
| cloudbed-2_q066 | 0,33 | 0,33 | 0,00 |
| cloudbed-2_q073 | 0,00 | 0,00 | 0,00 |

**1 miglioramento, 1 peggioramento, 6 pareggi.** Il delta medio positivo dipende dal caso `cloudbed-2_q053`; escludendolo *solo a titolo di sensibilità*, la differenza media sui sette casi rimanenti sarebbe −0,0714. Il caso **non** va escluso dal risultato ufficiale.

Su `cloudbed-2_q053` il baseline ha prodotto JSON analizzabile sintatticamente ma privo di `root cause reason`. Tale output originale è conservato e **non è stato corretto né rieseguito**. La conformità di formato è distinta dallo score ufficiale, che può riconoscere credito parziale con regole proprie.

## Limiti rispetto a PAVE e obiettivi futuri

L'attuale `src/harness/structural_temporal_verifier.py` osserva associazioni lessicali `node-N.servizio-replica` e confronta alcune anomalie nodo/container per famiglia di risorsa (CPU R01↔R07, memoria R02↔R08, read I/O R06↔R09). Questo **NON** equivale a:
- grafo dei veri archi RPC e delle dipendenze dei microservizi ricostruito dalle trace;
- verifica causale passo per passo e ricostruzione della propagazione verso il sintomo;
- conferma tramite interventi/fault injection e annotazioni causali PAVE di OpenRCA 2.0.

`causa_verificata=False` e `propagazione_verificata=False` restano corretti. Prossima estensione possibile: archi osservativi service→service da parent/child span, verifica temporale e di prestazioni con provenienza e stati `supportato`/`contraddetto`/`non_verificabile`, *senza presentare correlazioni come cause confermate*. Richiederebbe nuovo codice, test e protocollo.

Le tre classi mancanti per arrivare a R11 sono **R03** (`container network packet retransmission`), **R04** (`container network packet corruption`) e **R05** (`container network latency`). La loro fattibilità va verificata prima usando segnali GT-free, specialmente trace/log/mesh, senza presumere che un KPI diretto esista. Non inserire automaticamente tre regole basate su nomi di guasti; servono specifiche misurabili e test di falsi positivi. La documentazione Microsoft OpenRCA avverte che i guasti di rete spesso non sono rilevabili solo dai KPI e suggerisce relazioni di latenza tra span.

Se R03–R05 risultano implementabili, condurre una **nuova ablation R8 vs R11**, a parità di planner e ST, con casi development non riutilizzati e piano congelato. Non modificare né rieseguire lo studio R8/ST già concluso. Evaluation/OOD holdout devono restare riservati a una valutazione finale predefinita.

## Consultazione e dimostrazione senza costi API

- Aprire `docs/a1_verify_st_protocol_v1.md` per il disegno sperimentale e `src/evaluation/manual_paired_st_batch.py` per il preflight.
- Da Colab, sul codice sperimentale fissato (non un HEAD futuro): `%cd /content/Tesi_OpenRCA` e `!git checkout 138fb523efec4a665a2424ab2faedb698f10562e` **solo in una copia pulita/dedicata**, non sopra lavoro locale non salvato.
- Dopo il mount di Drive, leggere gli artefatti e verificare gli hash; la demo non necessita di `GEMINI_API_KEY`.
- **NON** invocare `--execute-pair` o `--confirm-api`: le 16 run sono concluse e il runner blocca i retry.
- Lo scoring già avvenuto può essere mostrato come risultato, non come una nuova valutazione o una misura blind.

Riferimenti: [OpenRCA originale](https://github.com/microsoft/OpenRCA), [OpenRCA 2.0 / PAVE](https://arxiv.org/abs/2606.27154).
