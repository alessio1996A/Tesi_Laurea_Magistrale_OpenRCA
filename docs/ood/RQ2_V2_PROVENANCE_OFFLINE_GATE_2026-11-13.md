# RQ2-V2 — Audit strutturale e gate OFFLINE prima di una nuova campagna

**Data:** 13 novembre 2026. **Stato:** candidato sperimentale, NON autorizzato a chiamare provider.

## Provenienza e isolamento

- Branch dedicato:
  `experiment/rq2-provenance-v2-offline-2026-11-13`.
- Creato a partire dal commit **`c0eee134a1219bb1704efb73621cafe3d4f70a1a`**
  del branch V1 `feature/ood-knowledge-transfer-audit-2026-11-10`.
- La campagna V1 rimane congelata: **39/72 artefatti discovery**
  e 32 claim reali con risultati, nessuna riscrittura.
- `src/agent/graph_engine.py`, `src/evaluation/experiment_runner.py`,
  `src/evaluation/rq2_evidence_bundle.py`, release RQ2,
  scoring RQ1, split e manifest non vengono modificati.
- Nessuna GT di discovery/test viene consultata qui.
  Nessuna API Sonnet, Haiku o Gemini viene invocata.
  OOD_TEST resta LOCKED.

## Causa tecnica documentata

Il runner V1 usa `AIMessage.tool_calls` e `ToolMessage`
ma nelle traiettorie `tool_trajectory` del ramo
`agent.graph_engine` salva soltanto nome/argomenti
o nome/risposta, **senza** `tool_call_id`.
Il bundle RQ2 fallisce chiuso se due chiamate
pendenti senza ID hanno lo stesso tool name.
Tre D Sonnet sono state effettivamente invalidate
con `AMBIGUOUS_TOOL_RESULT`, non per JSON finale
invalido o errori provider.

## Modifica candidata isolata

`src/agent/rq2_v2_graph_engine.py`:

- Reimpiega `crea_grafo_rca` e `testo_messaggio`
  originali, senza alterarne prompt e tool routing.
- Deriva la funzione `esegui_grafo_rca_v2` dal corpo
  congelato `esegui_grafo_rca`.
- Nella traiettoria `tool_call`, se presente,
  conserva l'`id` nativo della chiamata restituita
  da LangChain, come `tool_call_id`.
- Nella traiettoria `tool_result`, se presente,
  conserva l'attributo `ToolMessage.tool_call_id`.
- Non genera identificativi sintetici per chiamate
  prive di ID e non associa mai risultati per posizione.
- Lascia intatti `rq2_evidence_bundle.py`, i relativi
  controlli fail-closed e i record V1.
- **Non è ancora integrata** in un dispatcher RQ2-V2;
  perciò la sola presenza del modulo non cambia
  le esecuzioni effettuate dal runner RQ1.
  Qualsiasi futura integrazione richiede adapter,
  registrazione e preregistrazione separati.

## Sette test offline nuovi

File `src/tests/test_rq2_v2_tool_provenance_offline.py`:

1. Equivalenza V1/V2 di risposta, errori e metriche
   (eccetto durata) sui medesimi eventi sintetici.
   La proiezione della traiettoria V2 eliminando
   i soli `tool_call_id` deve coincidere con V1.
2. Due chiamate dello stesso tool, risultati
   volutamente invertiti: abbinamento esatto
   ID ↔ argomenti ↔ risposta.
3. Uso del vero LangGraph e del vero ToolNode,
   ma solo con LLM/tool finti, senza file/Market/API.
4. Mancanza di ID: nessuna invenzione, fallimento
   per ambiguità dei tool paralleli omonimi.
5. ID di risposta sbagliato: fallimento.
6. ID duplicato: fallimento.
7. Compatibilità legacy per singola chiamata
   senza ID: preservata.

**Non confondere la presenza di test con il loro esito:** i
test sono stati creati, ma non ancora eseguiti
nell'ambiente locale dell'utente.

## Istruzioni PyCharm (PowerShell)

Non modificare o usare Google Colab a questo punto.
In PyCharm aprire il progetto locale. Prima controllare:

```powershell
git status --short
```

L'output deve essere vuoto; se sono presenti modifiche
locali, **fermarsi** senza fare `reset`, `stash`
o sovrascritture automatiche.

Poi:

```powershell
git fetch origin
git switch --track origin/experiment/rq2-provenance-v2-offline-2026-11-13
git status --short
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_tool_provenance_offline.py" -v
```

Se il branch locale esiste già, usare `git switch
experiment/rq2-provenance-v2-offline-2026-11-13`
al posto di `git switch --track ...`.

**Atteso da verificare, NON ancora certificato:**
7 test offline. Se uno fallisce, inviare l'output;
nessun API pilot e nessuna modifica dati.

Solo **dopo** i sette test PASS, eseguire la regressione
del bundler V1 e il percorso reale LangGraph con fake:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_evidence_bundle.py" -v
python -m unittest discover -s src/tests -p "test_rq2_real_langgraph_fake_llm.py" -v
python -m unittest discover -s src/tests -p "test_rq2_protocol_identity_preflight.py" -v
```

Poi eseguire tutta la suite soltanto se le regressioni
mirate passano:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Verificare che `git status --short` non mostri
modifiche a file congelati.

## Gate scientifico NO-GO

**STOP e rivalutazione completa** se:

- la provenance degli ID non è verificabile
  nemmeno nei test offline con risultato invertito;
- risultato o metriche del runner divergono
  fra V1 e V2 oltre agli ID nella traiettoria;
- un ID mancante/sbagliato viene ricostruito per
  euristica anziché fatto fallire;
- falliscono test della pipeline esistente;
- l'adapter futuro richiede modifiche a V1, a
  documenti frozen, claim o record preesistenti;
- il tracciamento è formalmente valido ma
  conserva evidenze non utilizzabili/affidabili;
- non è possibile preregistrare una campagna
  distinta e un budget approvato prima di
  qualunque richiesta remota.

Se uno di questi punti si verifica, **non forzare** la
campagna corrente a 72/72. Congelare V1 come
campagna osservata e, se metodologicamente opportuno,
definire un nuovo esperimento indipendente con
split, versioni e contabilizzazione distinti.

## Gate dopo il PASS offline

Soltanto dopo un PASS verificato:

1. progettare un adapter V2 che sostituisca il solo
   esecutore diagnostico senza cambiare agente,
   payload del prompt, tools, budget e output contract;
2. verificare il percorso `run_experiment` di end-to-end
   con fake LLM e recorder V2 distinto;
3. fissare source SHA, split, seed/protocollo,
   no-retry, dichiarazione GT-free, criteri KPI,
   limiti di costo, gestione dei fallimenti;
4. concordare esplicitamente un **piccolo pilot reale**
   su una nuova campagna V2, mai sul claim V1;
5. confrontare V1 e V2 come campagne diverse,
   senza riclassificare retroattivamente gli
   `INVALID_OUTPUT` V1 come successi.

**Nessuna attività qui autorizza lo sblocco degli
11 casi OOD test o l'uso della GT per ottimizzare.**
