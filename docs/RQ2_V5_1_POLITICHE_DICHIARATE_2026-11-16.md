# RQ2 V5.1 — politiche dichiarate prima del run scientifico (16 novembre 2026)

Questo documento fissa le due regole che cambiano rispetto al pilota V5 e il
motivo. Va riportato nella tesi come "affinato sul pilota e congelato prima del
primo stage scientifico". Il pilota (archivio `data/rq2_v5_pilot_v1`) non entra
nei risultati.

## 1. Che cosa ha mostrato il pilota (18 stage, caso cloudbed-1_q032)

| Fatto osservato | Conseguenza |
|---|---|
| Sonnet A1_PAVE D: blocco ```json valido + paragrafo di commento dopo. Risposta non troncata (4.451 token di output su 5 chiamate). V5 la rifiutava (`REJECTED_WRAPPER`) e bloccava C e K. | Policy di formato V5.1 |
| Gemini A0 K: `PROVIDER_ERROR:GoogleAPIError`, 0 token. Rifatto 3 volte con lo stesso input (fuori archivio, diagnostica): 3 successi su 3. | Politica di retry |
| Haiku A1_PAVE D: blocco json valido, salvato dalla policy (`SINGLE_JSON_FENCE`). Tutte le risposte D di A0: JSON puro. | Le due deviazioni di D sono entrambe con A1_PAVE (n=2: osservazione, non risultato). |
| K completi: 1 `candidate` (Haiku A0), 3 `insufficient_evidence`. | `RECORDED_COMPLETE` misura il contratto, non l'utilità: il riepilogo ora distingue `candidate` da `insufficient_evidence`. |

## 2. Policy di formato V5.1 (`rq2_v5_1_single_json_fence_outside_text_v1`)

- Identica per tutti i modelli; nessun parametro per modello.
- Se la risposta contiene **esattamente un** blocco ```json (o ``` senza lingua),
  con fence di apertura e di chiusura su righe proprie, il testo passato al
  parser strict è il contenuto interno **inalterato**. Il testo fuori dal blocco
  è scartato ma resta nella risposta originale registrata (con SHA-256).
- Qualsiasi altro caso resta `REJECTED_WRAPPER` e viene rifiutato dal parser:
  due fence, lingua diversa da json, fence non chiusa, testo sulla stessa riga
  della fence, JSON interno rotto (mai riparato).
- Etichette di deviazione: `NONE`, `SINGLE_JSON_FENCE`, `FENCE_WITH_OUTSIDE_TEXT`,
  `REJECTED_WRAPPER`. Conformità **strict** = completo e `NONE`; **tollerante** =
  completo. Si riportano entrambe per ogni modello.
- Limite noto: se fuori dal blocco c'è un secondo JSON diverso, si usa sempre
  quello nel blocco (regola deterministica, dichiarata).

## 3. Politica di retry (`rq2_v5_one_transport_retry_v1`)

- Al massimo **un** secondo tentativo per stage, dentro lo stesso claim, con
  pausa di 10 s, stessa configurazione e stesso input.
- Solo se il primo tentativo è un errore di **trasporto senza output del modello**:
  C/K = eccezione dalla chiamata al provider (`PROVIDER_ERROR:*`); D = eccezione
  del grafo che non dipende dal comportamento del modello.
- Mai su `INVALID_OUTPUT`, `RECEIPT_REJECTED`, `PROTOCOL_ERROR:*`,
  `SDK_CONSTRUCTION_ERROR:*`, né su `AgentBudgetExhausted`, `AgentFinalizationEmpty`,
  `VerifyFinalizationToolCall`, `VerifyFinalizationEmpty`, `EmptyFinalResponse`,
  `GraphRecursionError`.
- Il primo tentativo resta nel record (`provenance.retry.attempts`: errore,
  durata, token). Il messaggio d'errore non è salvato, solo tipo e SHA-256.
- Conseguenza per le metriche: i token dello stage finale non includono quelli
  dei tentativi falliti; gli stage ritentati sono contati a parte nel riepilogo.
- Nota: in D lo stato `PROVIDER_ERROR` raggruppa anche errori di comportamento
  del modello (es. budget esaurito); il tipo d'errore nei tentativi li distingue.

## 4. Stato di verifica

- Verificato offline (sandbox, solo stdlib): normalizzazione, contratti C/K con
  la policy, runner, CLI, retry (classificazione e ciclo), riepilogo.
- Logica di retry dell'esecutore verificata con moduli finti (non LangChain vero).
- **Non ancora verificato** con LangChain/provider veri: i test marcati
  "serve LangChain" in `test_rq2_v5_stage_executor_offline.py` e
  `test_rq2_v5_executor_retry_offline.py` (da eseguire in PyCharm) e il run reale.

## 5. Cronologia da raccontare nella tesi

1. V4: Sonnet e Haiku avvolgono JSON valido in Markdown; il parser strict li rifiuta.
2. Audit in sola lettura delle risposte V4 → politica V5 (un solo fence), uguale per tutti.
3. Pilota V5 (archivio separato) → due problemi concreti (commento fuori dal
   fence; errore di trasporto transitorio).
4. V5.1 + retry unico, congelati prima del primo stage scientifico.

Entrambe le modifiche sono motivate a posteriori; sono dichiarate, uguali per
tutti i modelli e non toccano contratti, parser, prompt né dati.
