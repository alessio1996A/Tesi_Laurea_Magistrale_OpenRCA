# RQ2-V2 — Gate tecnico 841/841; GO offline, NO-GO live

**Data:** 13 novembre 2026.
**Fonte esito test:** riepilogo esecuzione locale PyCharm comunicato dall'utente.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Commit base V1 congelato:** `c0eee134a1219bb1704efb73621cafe3d4f70a1a`.
**Stato:** valutazione GO/NO-GO tecnica, NON release scientifica né autorizzazione API.

## 1. Risultato osservato

```text
Ran 841 tests in 72.153s

OK
```

La suite completa corrente ha superato **841 test su 841**.
Il precedente riepilogo era 817/817 prima degli 8 test
`test_rq2_v2_isolation_policy.py` e dei 16 test
`test_rq2_v2_synthetic_ledger.py`. Quindi:
**817 + 8 + 16 = 841**. La previsione intermedia di
833 aveva omesso gli otto test di isolamento.
I conteggi mirati NON vanno sommati nuovamente al totale 841.

L'output riassuntivo da solo non costituisce log completo
di tutte le asserzioni, ma il repository contiene le suite
e tutti i 841 test sono stati segnalati OK da unittest.

## 2. Integrità della branch

Confronto GitHub fra `c0eee134a1219bb1704efb73621cafe3d4f70a1a`
e `experiment/rq2-provenance-v2-offline-2026-11-13` eseguito il 13 novembre 2026:
**23 file aggiunti, zero file preesistenti modificati.**
Codice e fonti RQ2-V1, scorer, piani e archivio
risultati non sono stati sovrascritti da questo branch.

Il passaggio V2 sulla tool provenance usa un esecutore
aggiuntivo `src/agent/rq2_v2_graph_engine.py` che
conserva il vero `tool_call_id` delle tool call e dei
tool result. `rq2_evidence_bundle.py` è invariato
e resta fail-closed in caso di associazione ambigua.

## 3. Aspetti tecnici verificati offline

- Test di provenance del grafo V2, comprese due tool call
  omonime nello stesso round e risposte incrociate.
- Runner RQ1 originale attraversato con modelli/tool
  fake, senza invocazione SDK provider.
- Preparazione offline dello stage C vincolato al bundle.
- Catena D→C→K con fake driver e journal V1
  SOLO in directory temporanea con plan/source mock;
  restart, blocco delle dipendenze e no retry.
- Policy namespace V2: identificativi, radice separata,
  rifiuto stage V1 e OOD test.
- Nuovo store e claim journal `RQ2V2Synthetic*`,
  **indipendenti dalla persistenza V1** ma ancora
  deliberatamente limitati a fixture sintetiche:
  `data/rq2_v2_provenance/` con marker di sicurezza,
  JSON canonico, hash, create-only `O_EXCL`, blocco
  duplicati, integrità claim/record, fail-closed statuses,
  assenza di retry e analisi restart.

**Limite essenziale:** non è stata ancora effettuata
una prova end-to-end della pipeline COMPLETA
`run_experiment (fake) → esecutore V2 → nuovo journal/store V2`
con gli stessi artefatti sintetici. I test sopra
verificano sezioni contigue e singoli componenti,
non il dispatcher scientifico V2 completo.

## 4. Decisione GO/NO-GO al 13 novembre

| Area | Valutazione |
|---|---|
| Correttezza tecnica nei test offline | **PASS** |
| Integrità branch rispetto al V1 congelato | **PASS** |
| Progettazione preregistrazione V2 | **GO — offline only** |
| Release scientifica/archivio provider V2 | **NO-GO** |
| Pilot API a pagamento | **NO-GO senza nuovo gate e approvazione** |
| OOD test (11 casi) | **LOCKED** |
| Conclusioni sulla generalizzazione causale | **NON DIMOSTRATE** |

Il superamento dei test non autorizza una
spesa API, una diagnosi valida di OpenRCA
o la scrittura in un archivio V1.

## 5. Priorità: prossimo passo minimo necessario

**Non accumulare test senza una domanda verificabile.**
Prima di implementare altro codice o avviare API:

1. Completare un solo gate fake end-to-end che eserciti
   il **nuovo** store/journal V2 con D, C, K prodotti
   dal percorso fake e gli stessi meccanismi di
   provenienza e fallimento; conservare una prova
   di isolamento e no retry.
2. Definire quali nuove misure scientifiche servano
   realmente alla tesi: validità della tool provenance,
   attrition D/C/K, formalizzabilità K, differenze
   fra harness e modelli, costo/tokens e differenza
   fra osservabilità tecnica e diagnosi corretta.
3. Congelare **prima delle chiamate** source/release hash,
   schema claim V2 reale, coorte, comparatori, JSON/prompt,
   policy di errore e astensione, stop/budget e denominatori.
   Le quattro discovery sono già state viste nella V1:
   un nuovo pilot su quelle stesse osservazioni
   dimostrerebbe una correzione di robustezza tecnica,
   **non una generalizzazione indipendente**.
4. Solo dopo esito del gate, presentare al relatore
   una proposta circoscritta di pilot V2 e chiedere
   approvazione esplicita del budget API e del
   valore scientifico marginale rispetto a RQ1.
   Non presumere che 72 stage vadano rieseguiti.

## 6. Stato del lavoro congelato e deadline

RQ2-V1: **39/72 record discovery** registrati,
senza tentativi ripetuti o post-hoc riscrittura;
i fallimenti di provenienza osservati rimangono
parte dell'evidenza V1.

Gli **11 casi OOD test** rimangono non eseguibili
nella fase di sviluppo. Non accedere a GT,
scorer o nuove classi con il pretesto di
verificare l'archivio V2.

Scadenza tesi: **1 dicembre 2026**.
L'analisi RQ1 già completata costituisce
evidenza sperimentale da riportare con
grafici, limiti e confronto. RQ2 va
presentata come esplorativa finché le
prove non ne supportano una conclusione più forte.

Refactoring, commenti in italiano e pulizia
dei file solo **dopo** il freeze sperimentale,
senza alterare sorgenti o risultati referenziati.

**Decisione finale:** `GO_OFFLINE_PLANNING_ONLY`,
`NO_GO_LIVE_API`, `NO_GO_OOD_TEST`.
