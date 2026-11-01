# Verifica osservativa v0 — primo passo PAVE-inspired

## Stato del lavoro

La finalizzazione strutturata è stata verificata manualmente con
`gemini-3.5-flash-lite` su una risposta sintetica, senza accesso a OpenRCA.
Esito comunicato dall'esecuzione Colab del 2026-11-01:
- `SMOKE TEST STRUTTURATO: OK`
- JSON canonico con timestamp `2022-03-20 13:00:00`, componente `node-5`,
  reason `node CPU load` (valori sintetici)
- 200 token riportati dal provider, metrica disponibile
- durata 1.756 secondi
È un test di integrazione e non una misura di accuratezza RCA.

## Gate osservativo v0 (offline)

File: `src/harness/observational_verifier.py`.
Funzione: `verifica_coerenza_osservativa`.

**Input:** `RootCause` già prodotta dall'agente; report `unified_evidence_v2`
con eventuale sezione `regole_diagnostiche_v0`; finestra Unix
ufficiale, tolleranza temporale dichiarata.

**Output:** una verifica *osservativa*, non una certificazione causale.
Stati:
- `non_valutabile`: report o regole assenti;
- `fuori_finestra`: timestamp predetto esterno alla finestra;
- `nessuna_corrispondenza`: non ci sono candidati *riportati* con
  stesso componente e stessa classe;
- `tempo_non_corroborato`: componente e classe compatibili,
  segnale osservato temporalmente distante dalla predizione;
- `coerente_con_segnale`: candidata una corrispondenza lessicale e
  temporale con la telemetria.

Le verifiche usano il fuso `Asia/Shanghai` del benchmark. Le
identità dei componenti sono confrontate esattamente; per container
`node-5.frontend-0` si permette il nome `frontend-0` ma non si
confonde il nodo `node-5` con il container. La classe diagnostica è
confrontata lessicalmente, senza indovinare equivalenze o sinonimi.

La verifica non modifica la risposta, non legge ground truth e non
promuove nuove regole. `causa_verificata` resta sempre `False`:
una coincidenza temporale o un candidato R01-R11 non prova causalità.

## Limiti espliciti

1. Le regole R01, R02, R06-R11 coprono soltanto otto classi e potrebbero
   non identificare un guasto reale. Un report senza candidati non è una
   verifica negativa.
2. Alcuni candidati potrebbero essere omessi dal budget; riportiamo
   `candidati_omessi_per_budget` e `copertura_candidati_completa`.
3. La vicinanza temporale tra guasto predetto e segnale non dimostra
   che il segnale sia una causa; la differenza non prova che il guasto
   sia impossibile.
4. In questa v0 manca ancora una vera verifica della propagazione,
   una topologia validata e il confronto sistematico con ipotesi
   alternative; non va presentata come implementazione completa di PAVE.
5. Il gate è **disconnesso dal runner** fino a completamento dei test:
   nessun cambiamento all'accuratezza ufficiale, alla diagnosi o alla
   selezione dei tool.

## Passi successivi

- Eseguire la suite offline dopo l'aggiunta del gate.
- Progettare il contratto `VerificationResult` per componente,
  compatibilità temporale, evidenza favorevole/contraria/mancante.
- Aggiungere controlli strutturali/propagazione soltanto se supportati
  dalla topologia osservabile in OpenRCA.
- Integrare in una **nuova variante sperimentale** e confrontare su
  development senza usare i quattro incidenti già analizzati come
  verifica indipendente.
- Il trasferimento della conoscenza verrà eseguito *offline*, con
  provenienza, test indipendenti, versioni e gate di promozione, senza
  lettura delle etichette evaluation/OOD.

La documentazione è deliberatamente conservativa: evita di trasformare
la semplice presenza di anomalie in una falsa conferma causale.
