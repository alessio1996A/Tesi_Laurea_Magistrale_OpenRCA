# RQ2 — Esito post-pin offline su Google Colab

**Data:** 12 novembre 2026. **Fonte:** output eseguito dall'utente e comunicato in chat.
**Stato:** `RQ2_POST_PIN_OFFLINE_GATES_VERIFIED`. L'esito **non**
autorizza richieste a pagamento e **non** sblocca gli 11 test OOD.

## Evidenza esatta comunicata

```text
Mounted at /content/drive
CHECKOUT: CLONED
DEPENDENCIES: INSTALLED
GIT_HEAD: f15585bd62cd1bd1cdd0a88a06d0690a5131f67e
RELEASE_SHA256: a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52
TEST_OOD: LOCKED
LIVE_PROVIDER_REQUESTS: 0
STATUS: RQ2_POST_PIN_OFFLINE_GATES_VERIFIED
```

La cella effettivamente eseguita è documentata in
`docs/ood/RQ2_COLAB_POST_PIN_VERIFICA_MIRATA_2026-11-12.md`.
L'esito finale della cella (senza eccezioni) attesta il passaggio
dei controlli previsti: checkout su commit atteso, SHA del release
su Drive identico al JSON su GitHub, controllo dell'unico
blob Git del file di pin, match SHA-256 dei restanti 12 sorgenti
preregistrati, schema release tramite `_read_release` e verifica
del rifiuto del percorso D e C/K **senza** `confirm_paid_api=True`.
La riga di diagnostica `RELEASE_PIN_READBACK_AND_NO_CONSENT_GATES_OK`
non appare nell'estratto dell'utente: non attribuire un output testuale
non riportato, ma il successivo `STATUS` proviene dal completamento
della cella con `subprocess.run(..., check=True)`.

## Controlli e confini

- Il release scientifico immutabile è già stato installato su
  Google Drive in modalità create-only e verificato tramite readback.
- SHA-256 release: `a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52`.
- Pin esatto presente soltanto nel codice RQ2.
- Le 13 sorgenti originali RQ1 erano risultate immutate nel
  preflight finale del 12/11; nessuna modifica RQ1 in questa fase.
- `PLAN_STATUS="DRAFT_NOT_EXECUTABLE"` non rappresenta un
  dispatcher autonomo; lo stage live resta accessibile solo
  dal wrapper con consenso esplicito, claim e release firmato.
- La verifica non ha eseguito diagnosi, tool, scoring o provider:
  `LIVE_PROVIDER_REQUESTS=0`. Non confondere questi risultati con
  l'accuratezza su guasti OOD o con una prova di timeout HTTP reale.
- `test_unlocked=false`, test OOD **chiusi fino al separato freeze K**.
- I test PyCharm precedenti restano acquisiti; non rieseguirli
  per la sola registrazione documentale.

## Prossimo gate: consenso al primo singolo stage diagnostico

**Proposta specifica preregistrata:**

| Parametro | Valore |
|---|---|
| Provider | Google |
| Modello | `gemini-3.5-flash-lite` |
| Caso discovery | `cloudbed-1_q032` |
| Harness | `A1` |
| Stage | `D` (diagnosi), nessuna C/K automatica |
| Identità stage | `rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D` |

**Nessuna autorizzazione API già concessa.** Chiedere prima
all'utente un consenso **esplicito e circoscritto** alla D reale
su questa combinazione, sapendo che una D può comportare più
invocazioni del modello, che potrebbero avere costi; senza retry
automatici, con claim create-only prima della prima richiesta.
L'arm illustrativo RQ2-C resta `A1_8R + Sonnet`, scelto ex ante;
non adattare il protocollo ai risultati della prima discovery.

Dopo consenso: preparare una singola cella Colab di esecuzione
con verifica dell'esistenza di `Market.zip`, dell'identità di codice
e del release, della destinazione claim e degli esiti precedenti,
senza ritentare alcun claim ambiguo. **Mai** avviare gli 11 test
OOD prima del freeze indipendente delle regole K.
