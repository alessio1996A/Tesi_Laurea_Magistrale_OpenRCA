# Roadmap R8 → R11 — verifica di fattibilità prima dell'implementazione

**Stato:** studio progettuale; R03/R04/R05 **non** implementate o validate. Nessuna diagnosi Gemini e nessuno scoring nuovo è autorizzato da questo documento.

## Obiettivo

Estendere le otto regole attuali (R01, R02, R06–R11) solo se la telemetria OpenRCA 1.0 Market permette di costruire segnali osservativi attendibili per:

| ID | Categoria | Esempi di evidenza da verificare |
|---|---|---|
| R03 | container network packet retransmission | Contatori di ritrasmissioni, rapporto retransmit/packets se veramente disponibile; in alternativa indicatori indiretti da trace/log con stato non conclusivo |
| R04 | container network packet corruption | Errori/checksum/packet drops se misurati direttamente; degradazione RPC, proxy log e trace possono solo supportare un'ipotesi, non distinguere automaticamente corruzione da loss/latency |
| R05 | container network latency | Durate client/server da trace parent/child, proxy/mesh RTT o latency, baselines e variazioni temporali; attenzione alle conflazioni con lenta elaborazione server |

La FAQ di Microsoft OpenRCA indica esplicitamente che i guasti di rete spesso **non** sono identificabili con i soli KPI e suggerisce di confrontare latenze parent/child nelle trace: https://github.com/microsoft/OpenRCA.

## Fase A — inventario GT-free della telemetria

1. Leggere lo schema di `Market.zip` e l'elenco delle colonne e KPI **soltanto per finestre development ancora non utilizzate**; non aprire `record.csv`, `scoring_points` o `query.csv` per progettare regole.
2. Per ciascuna delle tre categorie documentare: nome misurato, livello container/service/node, unità, campionamento, provenienza, tempo/finestra, copertura, dati mancanti.
3. Ispezionare i formati di `metric_container.csv`, `metric_node.csv`, `metric_mesh.csv`, `trace` e `log` limitatamente a data schema e segnali osservativi consentiti.
4. Verificare se esistono realmente contatori **specifici** per retransmission e corruption. Se non esistono, non inventare una misura né denominare `R03`/`R04` un euristico generico che confonde diversi guasti.
5. Documentare la possibilità di identificare servizi tramite trace, senza attribuire causalità alla sola dipendenza temporale.

Output richiesto: `network_signal_inventory_v1.json` con fonti e coperture, *senza* etichette o risposte per caso.

## Fase B — specifiche e test offline

Per ogni regola proposta, registrare:
- precondizioni e indicatori ammessi;
- baseline e unità: differenti metriche non devono essere trattate come percentuali se sono contatori o durate;
- soglie motivate indipendentemente dalle etichette di ground truth;
- output `candidato_da_verificare` / `nessun_candidato` / `evidenza_insufficiente`, con provenienza e limiti;
- test su segnali negativi (CPU/memoria e latenza applicativa, dati mancanti, campionamento, timestamp ms/s, container ambiguo, retry client/server);
- nessuna promozione di regola basata sul solo risultato finale dello scorer o sui casi development precedentemente valutati.

**Gate:** regola non supportata se non esiste un segnale sufficientemente discriminante; fino ad allora mantenere R8. Test sintetici provano la correttezza software, non l'accuratezza su guasti reali.

## Fase C — esperimento nuovo, mai overwrite

Solo per le regole effettivamente implementabili:
- creare **nuovo branch** dopo il commit congelato `138fb523efec4a665a2424ab2faedb698f10562e` e testare offline;
- confronto appaiato **R8 vs R8+regole aggiunte** a budget, prompt, planner, ST, modello e parametri controllati;
- per isolare l'effetto informativo delle regole, tenere fisso A1_VERIFY_ST e cambiare **solo** il report rule-based; niente nuova modifica PAVE nello stesso test;
- preregistrare nuove finestre development senza sovrapposizioni con piloti/coorti gia' viste;
- nuova procedura di freeze prima dello scoring, new run IDs, nessun retry automatico, output originali preservati;
- evitare di guardare evaluation/OOD per decidere regole o soglie. L'eventuale OOD blind è una fase finale separata.

Se una o più regole falliscono il gate di fattibilità, riportare il risultato negativo nella tesi. L'obiettivo non è arrivare al numero 11 a ogni costo, ma aumentare **copertura osservativa affidabile**.

## Fase D — PAVE-inspired path verification, esperimento separato

Un grafo di dipendenze RPC derivato da parent/child span e association service/container/node può sostenere catene osservabili candidato causa → degradazione locale → effetti downstream. Per ogni arco servono provenienza, confronto temporale, anomalie RPC e stato `supportato`/`contraddetto`/`non_verificabile`. Questa procedura **non** conferma causalità senza interventi e non deve essere mischiata con la nuova ablation R8→R11.

Riferimento PAVE: https://arxiv.org/abs/2606.27154.


---

## Esito osservativo della Fase A — 3 novembre 2026

La Fase A è stata eseguita attraverso gli audit A/1–A/6, su **quattro finestre development già osservate** (due per cloudbed), senza lettura della ground truth durante l'audit e senza nuove chiamate Gemini. Il codice e i test si trovano sul branch `feature/r03-r05-feasibility-schema-v1`.

- **R03:** 720/720 coppie numeriche allo stesso timestamp e nodo (274 con entrambi i KPI positivi). Metriche **node-level**, insufficienti per diagnosticare la causa su un container; unità e semantica del KPI non ancora verificate.
- **R04:** 720/720 profili errori/drop tutti zero nelle finestre considerate. Nessuna variabilità discriminante e nessuna prova specifica di packet corruption.
- **R05:** 33.960/33.960 coppie durata/richieste Istio con stesso componente, suffisso e timestamp (14.679 entrambe positive). Durata RPC non equivale a sola latenza di rete.

**Gate A→B non superato** per promuovere automaticamente R03, R04 e R05 a detector di cause container-level. Restano **otto regole deterministiche**. R03 potrebbe diventare un indizio ausiliario a livello nodo; R04 è sospesa; R05 richiede eventuale studio separato delle trace, senza inferenza causale immediata. Non avviare la Fase C o un nuovo esperimento senza protocollo concordato.

[Relazione integrata per il professore](RELATORE_PRESENTAZIONE_INTEGRATA_2026-11-03.md) · [Nota tecnica GT-free](network_r03_r05_feasibility_relatore_2026-11-03.md) · [Notebook grafici Colab](../notebooks/Colab_Relatore_Risultati_e_Regole_2026_11_03.ipynb)
