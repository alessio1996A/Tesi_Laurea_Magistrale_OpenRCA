# Piano di pulizia del repository per il relatore

**Obiettivo:** mostrare un percorso chiaro dal dataset al risultato, senza
cambiare l'algoritmo sperimentale, le predizioni già congelate o lo scoring.

## Architettura attiva — mantenere

- `src/agent/`: factory del modello, grafi LangGraph, prompt, cinque tool,
  mappa di etichette di presentazione.
- `src/harness/`: evidence builder, sintesi, report, regole, planner,
  contesto strutturale/temporale.
- `src/output/`: parsing e contratto V2 per i sette task.
- `src/evaluation/`: config, experiment runner, runner e audit V3.
- `src/tests/`: regressione di tool, harness, output e protocollo.
- `docs/`: indice e architettura corrente; documentazione storica conservata.
- `Market.zip`, manifest e JSON delle run: **solo Drive**, non nel Git.

## Regole della pulizia

1. Il commit `6747eecc77c1b2fff7d581c7284578b5c574b4f7`
   non viene modificato né sostituito nei metadati sperimentali.
2. I nomi scientifici interni restano invariati; introdurre soltanto
   alias di presentazione, senza cambiare import, path o JSON.
3. Conservare i test anche quando i nomi ricordano esperimenti storici;
   possono verificare compatibilità e correttezza.
4. Eliminare soltanto gli script di **patch manuale una tantum** che non
   vengono importati dal codice attivo e la cui trasformazione è già stata
   applicata al runner. Il file rimane recuperabile al commit congelato.
5. Non eliminare automaticamente runner e documenti storici finché
   non siano stati verificati tutti i riferimenti e i test su PyCharm.
6. I commenti e le docstring possono essere tradotti in italiano, senza
   modificare le stringhe del prompt inglese, nomi API, identificativi
   di benchmark o etichette dei guasti.
7. La demo deve essere di sola lettura; nessun replay è una nuova run
   sperimentale fatturata.

## Controlli di qualità da eseguire dopo il checkout

```bash
python -m compileall -q src
PYTHONPATH=src python -m unittest discover -s src/tests -p 'test_*.py' -v
```

Per PyCharm su Windows, impostare `src` come Sources Root oppure
configurare `PYTHONPATH=src` nell'ambiente di test.

**Nota operativa:** i test completi dell'intero repository non possono
essere dichiarati superati senza eseguirli nell'ambiente con le dipendenze
installate. La sola modifica documentale non dimostra l'assenza di regressioni.

## File storici rimossi dal branch di presentazione

Questi script non fanno parte della pipeline della campagna V3:

- `src/evaluation/A0_OpenRCA.py`: script monolitico pilota storico;
- `src/evaluation/A1_OpenRCA.py`: script Colab monolitico A1-v1;
- `tools/apply_a1_rule_batch_patch.py`: patch manuale una tantum,
  gia' incorporata nel runner centrale.

I tre file sono stati rimossi **soltanto dal branch corrente**, non dal
commit sperimentale congelato `6747eecc77c1b2fff7d581c7284578b5c574b4f7`,
da cui restano recuperabili. Le interfacce attive `experiment_runner.py`,
`v2_campaign_runner.py`, i grafi, le regole e i risultati non sono stati
modificati da queste cancellazioni.

La rimozione e' una semplificazione dell'albero per la presentazione;
richiede comunque il test completo di regressione prima di considerare
concluso il refactoring.

## Spostamenti rimandati

Gli script di pilota e le note di esperimenti precedenti possono essere
spostati in un archivio versionato dopo una scansione delle importazioni.
Non spostare in massa `src/evaluation/` o `src/tests/`: ciò rischierebbe
di rompere test e import per un vantaggio prevalentemente estetico.
