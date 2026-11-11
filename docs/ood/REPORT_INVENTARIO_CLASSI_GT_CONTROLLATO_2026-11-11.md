# Fase 2 — Inventario controllato delle quattro classi OOD
**Data:** 11 novembre 2026  
**Evidenza:** output Colab fornito dall'utente, script `src/evaluation/ood_class_inventory.py` eseguito al commit `751cbd5b1b7a76c477f73ae7e56ba9e758de301f`.  
**Tipo di audit:** lettura intenzionale del ground truth in un modulo *isolato di valutazione*; report **solo aggregato**, nessuna associazione query–etichetta divulgata. **Nessuna inferenza LLM, nessun punteggio e nessuna selezione discovery/test eseguiti.**

## 1. Verifica delle sorgenti e della tracciabilità

- `audit=ood_class_inventory_controlled_gt_v1`, `source_verified=true`, `classification_status=complete`.
- Split SHA256: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest SHA256: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Cloudbed-1: `query.csv` 70 righe, SHA256 `3512ba2d72648f251e7e01733f079c492a4ff573de557a0223ea538bd9c06742`; `record.csv` 70 righe, SHA256 `6246b65915ecaa948037875a149a3d50afdc730371c8b4e3785799995d589324`.
- Cloudbed-2: `query.csv` 78 righe, SHA256 `140300e5edfe287a60944dedeaed08291c298bcc672a070a0630b2835f5a5aee`; `record.csv` 78 righe, SHA256 `b12d8c91518cf31e10fdce3ce2e6d38fe259013b73ed9460635022afc12f6162`.
- Verificato l'allineamento fra query/record e manifest congelato per tutte e **148** le query.
- Nelle 15 query OOD: `known_target_reason_query_count=15`, `unrecognized_reason_query_count=0`. Nomenclatura delle quattro classi riconosciuta integralmente.
- `read_ground_truth=true`, `read_query_scoring_points=true`, `read_telemetry=false`, `read_predictions=false`, `model_api_calls=0`, `files_written=false`, `emits_case_label_mapping=false`.

## 2. Risultati aggregati — quattro classi riservate

| Classe di guasto | Query OOD | Gruppi temporali entro classe | Task che chiedono reason | Cloudbed-1 | Cloudbed-2 |
|---|---:|---:|---:|---:|---:|
| node CPU spike | 3 | 3 | 1 | 2 | 1 |
| container write I/O load | 3 | 3 | 2 | 0 | 3 |
| container process termination | 4 | 4 | 2 | 2 | 2 |
| container packet loss | 5 | 5 | 3 | 2 | 3 |
| **Totale** | **15** | **15 somma delle appartenenze classe-gruppo** | **8** | **6** | **9** |

**Nota fondamentale:** il totale delle appartenenze per classe (15) **non coincide** con i 14 gruppi temporali globali, perché una finestra contiene due query associate a **classi differenti**. Il preflight GT-free ha identificato la finestra condivisa da `cloudbed-1_q014` e `cloudbed-1_q030`. Il presente report **non** pubblica le classi attribuite ai due casi. Non separarli tra discovery/test.

## 3. Interpretazione e limiti

1. Tutte le **4 classi OOD** sono rappresentate, ma con campioni piccoli (3,3,4,5 query). Non è ancora dimostrato che corrispondano a 15 episodi fisici indipendenti; avere 14 gruppi temporali disgiunti **non dimostra** l'indipendenza delle iniezioni.
2. Solo **8/15** task OOD richiedono esplicitamente il `reason` nello scoring Microsoft: il successo dei restanti 7 task **non** dimostra da solo riconoscimento della classe. Definire **prima delle inferenze** una metrica di diagnosi per classe e una metrica distinta di pseudoregola, mantenendo il confronto con lo scorer ufficiale sui task originali.
3. `container write I/O load` compare solo in cloudbed-2: **non è possibile** sostenere una generalizzazione cross-cloudbed di questa classe sulla coorte disponibile.
4. Per le classi con tre query è verosimile che un test di generalizzazione sia statisticamente fragile; servono controlli negativi e criterio di indipendenza del guasto. Non attribuire precisione statistica sproporzionata.
5. Il modulo di inventario GT deve restare isolato dai tool, prompt e processi degli agenti. Non esportare il mapping `case_id → reason` nel repository sperimentale, nelle celle LLM, negli output visibili di addestramento o nei prompt.
6. **Nessuna decisione ancora congelata** sulle configurazioni harness (`A1_8R` principale e `A0` controllo sono una proposta), sulle modalità di discovery/test, sui casi da utilizzare per generare pseudoregole e sui budget API.

## 4. Decisione operativa provvisoria

**Non allargare ancora arbitrariamente il campione.** Il Market di cloudbed-1/cloudbed-2 contiene in totale 70+78=148 query, già allocate nei quattro split originali. L'eventuale ampliamento richiede identificazione di nuove sorgenti/coorti e un protocollo distinto: non riciclare a posteriori development/evaluation/mixed_quarantine come *nuovo test indipendente*.

Prima di inferenza, eseguire un **audit offline di dipendenza degli episodi** (possibili collisioni per tempo, componente, categoria, fault injection e sessione, senza associare classi a `case_id` negli output pubblici), quindi preregistrare la separazione discovery/test per *gruppi di incidente*; se i casi non consentono un holdout ragionevole, limitare la conclusione a feasibility e validazione esplorativa, non a generalizzazione dimostrata.

## 5. Documentazione per la tesi

Conservare la distinzione fra **query, task, record di guasto, finestra temporale, gruppo di finestre e episodio indipendente**. Riportare integrità delle sorgenti, SHA, conteggi, motivazioni della partizione, impossibilità di generalizzazione cross-cloudbed per I/O write, separazione ground truth vs agente, risultati in forma statistica adatta a n molto piccolo. Non retrodatare né attribuire a un protocollo già congelato decisioni ancora esplorative.
