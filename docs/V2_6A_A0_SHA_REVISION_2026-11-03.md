# V2.6A — Correzione preregistrata del controllo SHA per il braccio A0

Data: 3 novembre 2026. Stato: revisione del codice da testare prima di una nuova run reale.

## Incidente pre-API

Sul piano congelato originale:
- protocollo: `openrca_harness_v2_five_agents_development_v1`;
- commit: `c7a71c66ce798834cacaaa3f1495f2e756efcc9c`;
- hash SHA-256 del piano: `b5444e85335e273e71cb08326c5988469af992cfe7d1d5f2d79562abeb806d01`;
- primo run ID previsto: `openrca_harness_v2_five_agents_development_v1__cloudbed-1_q005__a0__r01`.

Il primo tentativo ha fallito con `ValueError: SHA delle evidenze preprocessate mancante`. L'esecuzione si è arrestata nel metodo `execute_exactly_one`, al controllo sull'hash del preprocessing, **prima** di `_exclusive_json(claim, ...)` e **prima** dell'invocazione di `run_experiment`. Pertanto **nessuna inferenza Gemini** è stata invocata da quel tentativo. La creazione del claim e dei file di risultato deve comunque essere verificata sul disco prima di procedere.

La causa è riproducibile dal codice: `prepara_esperimento` assegna `evidence_report=None` e `evidence_sha256=None` per `A0` (baseline senza harness deterministico). L'errore era dovuto al controllo uniforme che esigeva un hash SHA-256 da **tutti e cinque** gli agenti, violando la definizione di A0. I test fake-LLM precedenti usavano un hash non nullo sintetico anche per A0, quindi non coprivano l'invariante del braccio baseline.

## Correzione

- In `src/evaluation/v2_campaign_runner.py` `execute_exactly_one`, prima del claim:
  - per **A0** si richiede `evidence_sha256 is None`;
  - per A1_V2, A1, A1_VERIFY, A1_VERIFY_ST si richiede SHA-256 esadecimale di 64 caratteri.
- `_integrity_issues` applica lo stesso schema al risultato finale.
- Il valore `None` è registrato come `null` nei JSON di claim e risultato per A0, senza creare hash fittizi.
- Aggiornati i test `test_v2_campaign_runner.py` con fixture A0 senza report e due casi di rigetto prima della chiamata API.
- **Nessun cambiamento** a dataset, seed, split, selezione degli otto incidenti, prompt, tool, regole, budget, modello o scoring.

## Versionamento del freeze

NON si altera il vecchio piano `_v1`: resta valido come documento dell'errore metodologico, non come piano di esecuzione da riprendere.

Il protocollo corretto si chiama
`openrca_harness_v2_five_agents_development_v2`.

La stessa selezione GT-free di otto incidenti è ristampata in un **nuovo** file `data/protocols/v2/openrca_harness_v2_five_agents_development_v2_plan_v1.json`. I 40 nuovi run ID contengono il protocollo `..._v2`; i file di output vanno in una nuova sottocartella del protocollo v2. Non si riutilizzano né si sovrascrivono gli output/claim del protocollo v1.

Il freeze v2 deve essere creato **solo dopo**:
1. esecuzione di tutti i test `test_v2*.py` (ora **70** previsti);
2. controllo nel Drive della mancata creazione di claim/output v1 per il tentativo fallito;
3. nuova anteprima `evaluation.v2_preregister` con il commit HEAD corretto;
4. creazione create-only con `--write`;
5. nuovo preflight: 8 `ready` e 32 `waiting_for_previous_variant` e nuovo SHA del piano.

Non copiare il vecchio SHA nel piano corretto: bisogna leggere quello restituito dalla nuova procedura di freeze.

### Nota scientifica

L'agente A0 misura la baseline senza evidenze deterministiche. Il confronto è metodologicamente valido soltanto se l'assenza del report rimane esplicita, senza fabbricare uno SHA artificiale. Conserviamo la traccia del tentativo fallito e della modifica per garantire auditabilità.

Nessun run è stato ripetuto automaticamente e nessun dato V1 è stato modificato.
