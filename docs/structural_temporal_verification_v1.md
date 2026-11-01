# Verifica strutturale e temporale v1 — piano PAVE-inspired

**Stato:** modulo puro/offline, non integrato nel runner e non utilizzato per modificare le predizioni. Richiede verifica dei test in PyCharm.

## Motivazione

Il verificatore osservativo v0 individua corrispondenze fra diagnosi e candidati delle otto regole, ma non controlla separatamente:
- il livello di una causa prevista (nodo vs container);
- l'ambiguita' di una identita' container non qualificata;
- la contemporaneita' o successione di due anomalie osservate allo stesso livello host/container;
- la compatibilita' della *famiglia di risorsa* tra i segnali confrontati.

Una diagnosi sul nodo NON puo' essere considerata equivalente a una diagnosi sul container: `node-5` e `node-5.frontend-0` non sono la stessa entita'.

## Implementazione

Modulo: `src/harness/structural_temporal_verifier.py`.
API: `verifica_relazioni_strutturali_temporali(root_cause, evidence_report, start_unix, end_unix, tolleranza_secondi=60)`.

Partendo dalla verifica osservativa v0 e dal report `regole_diagnostiche_v0`, il modulo:
1. Controlla gli identificativi di telemetria di nodo e container.
2. Associa solo container con identificativi espliciti `node-N.nome-container` al relativo nodo. **Questa associazione lessicale non certifica una topologia Kubernetes.**
3. Se `frontend-0` compare su piu' nodi, restituisce `host_ambiguo` anziche' sceglierne uno.
4. Restringe le relazioni alle stesse *famiglie di risorsa*, dove il confronto e' effettivamente disponibile a entrambi i livelli:
   - R01 container CPU / R07 nodo CPU;
   - R02 container memoria / R08 nodo memoria;
   - R06 container read I/O / R09 nodo read I/O.
   Le regole R10 e R11 rimangono valide come candidati su nodo, ma **non esiste in questa versione una controparte container esplicita** con cui formare automaticamente una relazione della stessa famiglia.
5. Confronta il primo segnale per nodo e container: nodo precedente, container precedente o quasi contemporanei (tolleranza dichiarata).
6. Fornisce indici di provenienza per ogni coppia osservata e non altera nessun report.

## Semantica

Stati indicativi: `relazioni_osservate`, `nessuna_relazione_osservata`, `host_ambiguo`, `host_non_osservato`, `classe_non_coperta`, `livello_non_verificabile`, `fuori_finestra`, `non_valutabile`.

Gli stati NON rappresentano:
- `causa_verificata` (sempre falso);
- `propagazione_verificata` (sempre falso);
- una verifica della dipendenza fra servizi;
- un criterio per correggere automaticamente il componente o l'istante del guasto.

Un ordine temporale compatibile e un'omonimia dei segnali NON dimostrano causalita'; segnali mancanti o casi non coperti NON dimostrano assenza di guasti. Se il detector non riporta candidati per un budget o classi mancanti, questa limitazione continua a valere.

## Prossimi passi

- Test sintetici offline (anche casi negativi) su PyCharm, senza Gemini.
- Validazione su dati di sviluppo **non contaminati dalla ground truth** del nuovo ciclo sperimentale.
- Solo dopo, se i dati lo consentono, verifiche su dipendenze applicative dai segnali Mesh/trace, con rappresentazione separata di relazioni osservate e inferite.
- Un nuovo braccio sperimentale (non A1/R8 storico) per misurare utilita' e costi; nessuna lettura delle risposte evaluation/OOD prima del freeze.

Il trasferimento della conoscenza resta una fase distinta: un candidato non puo' essere promosso a regola solo perche' supera controlli lessicali e temporali.
