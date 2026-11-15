# RQ2-V2 — Audit offline del rischio di estrazione multi-blocco JSON (2026-11-15)

**Natura:** evidenza tecnica documentale, **non** modifica del protocollo o dei risultati sperimentali. Sorgenti scientifici pinnati `f0b64a36b08c2ae5db424b544965db5362190377`; release `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`. Il record C Gemini A0 `cloudbed-1_q032` resta `INVALID_OUTPUT` (record SHA `51946d926aa2a5a0f9dd2ba997d8565116ef8158a2af44df5d0051d73ee3f4b1`); record K resta `BLOCKED_DEPENDENCY`, senza chiamata API.

## Domanda di fairness

Evitare che errori della nostra integrazione dei content block siano confusi con difetti intrinseci di uno specifico modello (Gemini, Sonnet, Haiku), compromettendo il confronto della qualità diagnostica e del trasferimento della conoscenza. Il contratto C/K richiede JSON rigoroso; l'astensione è ammessa.

## Test locale offline comunicato dall'utente

Contesto: PyCharm / PowerShell `PYTHONPATH=src`; import di `agent.graph_engine.testo_messaggio` e `json.loads`. Primo incollaggio ha provocato un errore di rendering di PSReadLine (`ArgumentOutOfRangeException`), non un risultato Python. La **seconda esecuzione** ha prodotto:

```text
STRINGA_UNICA: VALID_JSON
OUTPUT: '{"schema_version":"rq2_cause_probe_v0"}'
BLOCCO_UNICO: VALID_JSON
OUTPUT: '{"schema_version":"rq2_cause_probe_v0"}'
DUE_BLOCCHI: INVALID_JSON
OUTPUT: '{"schema_version":"rq2_cause\n_probe_v0"}'
```

I due blocchi simulati erano:
```python
[
  {"type": "text", "text": '{"schema_version":"rq2_cause'},
  {"type": "text", "text": '_probe_v0"}'}
]
```

Nel codice congelato `testo_messaggio(contenuto, solo_testo=True)`, per `list` di blocchi `text`, usa `"\n".join(parti)`. Pertanto **è dimostrato** che l'adattatore può introdurre una nuova riga dentro un valore JSON precedentemente continuo, rendendolo sintatticamente invalido. L'esatta posizione corrisponde al punto di newline nel record Gemini C osservato.

**Non è dimostrato** che il provider abbia effettivamente restituito due blocchi in quella chiamata: il record conserva il raw_response *dopo* l'estrazione testuale, non gli `AIMessage.content` originali. Il modello potrebbe aver generato direttamente una newline non valida. Il test sintetico non consente l'attribuzione retroattiva dell'errore al software.

## Decisioni e prossime verifiche

1. Nessuna modifica ai raw response, ai record create-only, ai loro SHA, al protocollo scientifico RQ2-V2 o a RQ1; non rifare D/C né K bloccato.
2. Sospendere ulteriori stage pagati fino a un audit offline del trasporto e della serializzazione condivisi: verificare rappresentazioni reali attese dagli SDK, testare blocchi text validi e multipli, preservare semantica e confini; distinguere multi-block arbitrari da chunk che ricostruiscono lo stesso testo.
3. Non cambiare `"\n".join` in `"".join` senza analisi: anche questa scelta potrebbe mutare output legittimi; progettare una policy uniforme, verificabile e applicata **a tutti e tre** i modelli.
4. Se occorre una correzione del comportamento di estrazione, svilupparla su branch/versione scientifica distinta, con test offline e nuovo freeze prima di ulteriori live run; risultati V2 preesistenti rimangono separati, mai riparati.
5. Nel confronto scientifico distinguere `provider error`, `JSON/contract validity`, `abstain`, accuratezza/validità causale e costo token; non trattare automaticamente `INVALID_OUTPUT` come diagnosi sbagliata o incapacità causale.
6. Nessuna nuova API avviata in questo audit; 11 OOD bloccati; budget operativo USD 100.00 già deliberato. Nessuna nuova richiesta di paper/trascrizione per la diagnosi tecnica.
