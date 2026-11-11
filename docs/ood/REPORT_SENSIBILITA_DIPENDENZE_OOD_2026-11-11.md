# Fase 2 — Audit di sensibilità delle dipendenze fra eventi OOD
**Data:** 11 novembre 2026  
**Fonte verificabile:** output Google Colab riportato dall'utente, codice `src/evaluation/ood_dependency_sensitivity.py`, eseguito al commit `a732773dcee3bfd2152c3d79432c5a56fb9e982d`.  
**Stato:** audit offline concluso, **non** protocollo discovery/test congelato.

## 1. Provenienza e garanzie

- `audit = ood_dependency_sensitivity_controlled_gt_v1`; `source_verified = true`.
- Split congelato SHA256: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest congelato SHA256: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- 15 query OOD; 1 coppia con sovrapposizione di finestra; 14 gruppi temporali.
- Il ground truth di `record.csv` è stato intenzionalmente letto **solo dall'audit offline di valutazione**. Nessuna mappatura `case_id → reason` è stata stampata; `read_telemetry=false`, `read_predictions=false`, `model_api_calls=0`, `files_written=false`.
- I 5 test sintetici del modulo dipendenze e i 5 test sintetici del modulo inventario sono risultati **OK in PyCharm**, secondo l'output precedentemente fornito dall'utente. Non sono prove della validità causale del proxy.

## 2. Risultati — soglie di prossimità

Il proxy considera un'ulteriore coppia candidata se sono uguali **cloudbed, classe (reason), componente** e la differenza assoluta fra i timestamp dei record non supera la soglia. Le sovrapposizioni delle finestre sono sempre raggruppate, anche quando le due classi sono differenti.

| Soglia (secondi) | Minuti | Gruppi candidati di dipendenza | Coppie stesso reason/componente entro soglia | Coppie aggiuntive oltre overlap |
|---:|---:|---:|---:|---:|
| 0 | 0 | 14 | 0 | 0 |
| 1800 | 30 | 14 | 0 | 0 |
| 3600 | 60 | 14 | 0 | 0 |
| 7200 | 120 | 14 | 0 | 0 |
| 14400 | 240 | 14 | 0 | 0 |

Distribuzione dimensioni dei gruppi **identica per ogni soglia**: 13 gruppi di una query e 1 gruppo di due query. Per tutte le soglie, gruppi che contengono ciascuna classe:
- node CPU spike: 3;
- container write I/O load: 3;
- container process termination: 4;
- container packet loss: 5.

La somma 3+3+4+5=15 è maggiore dei 14 gruppi globali perché il gruppo di due query include **due classi distinte**; non sono 15 episodi indipendenti.

## 3. Interpretazione prudente

L'audit **non rileva ulteriori coppie** che condividono cloudbed+classe+componente con prossimità fino a quattro ore. Non significa che tutti i restanti gruppi rappresentino iniezioni di guasto fisicamente indipendenti: potrebbero esistere dipendenze di scenario, workload, campagne di injection, sottosistemi comuni o altre correlazioni non viste dal proxy. La coppia `cloudbed-1_q014`/`cloudbed-1_q030` **deve restare unita** in qualunque eventuale partizione discovery/test.

Inoltre solo 8 delle 15 query OOD richiedono espressamente il campo `reason` secondo i task originali; la misurazione della diagnosi di **classe** per tutte le query richiede un output aggiuntivo preregistrato, separato dallo scoring Microsoft, e non va equiparata al successo dei task temporali/componenti.

## 4. Implicazioni sperimentali ancora da decidere

- L'inventario dà 3/3/4/5 query nelle quattro classi; qualsiasi split discovery/test per classe sarà piccolo e fragile. Per la classe `container write I/O load` tutti i tre record sono su cloudbed-2: nessuna validazione cross-cloudbed disponibile per questa classe.
- Prima delle chiamate Gemini/Claude definire chiaramente **due valutazioni**: (a) diagnosi di classi non codificate; (b) proposta e validazione di pseudoregole deterministiche. La seconda richiede separazione dei gruppi per non riutilizzare la stessa evidenza.
- Non modificare retroattivamente RQ1 e gli esperimenti EVALUATION20. Non riutilizzare `development`, `evaluation` e `mixed_quarantine` come nuovi test indipendenti senza un nuovo protocollo con dichiarazione delle limitazioni.
- Le alternative di harness `A1_8R` principale e `A0` controllo rimangono **proposte da fissare prima della campagna**, non decisioni già congelate. Gemini → Sonnet → Haiku a parità di coorte e prompt fissati, senza usare i risultati Gemini per ottimizzare sullo stesso test.
- Nessun agente è stato ancora avviato sui 15 OOD, nessun campione è stato assegnato a discovery/test e nessuna regola è stata proposta o valutata in questa fase.

**Prossimo passo:** progettare e documentare il protocollo RQ2 (unità di indipendenza, separazione discovery/test, criteri di campionamento, metrica diagnosi, forma e verifica della pseudoregola, controlli negativi, limiti statistici, confronto modelli, budget). Le decisioni non vanno dichiarate definitive prima di approvazione.
