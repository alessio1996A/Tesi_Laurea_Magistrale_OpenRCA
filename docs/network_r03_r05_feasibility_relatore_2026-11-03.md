# Nota tecnica per confronto con il relatore — OpenRCA Market 1.0

**Data:** 3 novembre 2026  
**Stato:** evidenze GT-free di fattibilità, non validazione di regole RCA  
**Branch sperimentale non congelato:** \`feature/r03-r05-feasibility-schema-v1\`  
**Baseline A1/ST congelata:** commit \`138fb523efec4a665a2424ab2faedb698f10562e\`  
**Scadenza prevista della tesi:** 1 dicembre 2026

> Fonte dei numeri: output Colab A/2–A/6 riferiti dall'autore della tesi; questa nota li trascrive per la discussione. I JSON integrali di audit restano nell'ambiente Colab finche' non sono archiviati in modo esplicito. Non sostituisce la verifica su artifact integrali.

## 1. Problema e contributo

Il progetto studia una pipeline RCA basata su LLM e strumenti/strumentazione (harness engineering) sul benchmark OpenRCA Market 1.0. La baseline sperimentale usa **8 regole deterministiche** gia' implementate e risultati storici congelati; un'estensione proposta riguarda tre classi non coperte direttamente da quelle regole:

- **R03: packet retransmission** a livello container.
- **R04: packet corruption**.
- **R05: network latency**.

La disponibilita' di 15 classi di guasto nel benchmark non implica automaticamente che tutti i guasti siano riconoscibili con una regola GT-free dalle metriche esposte.

**Domanda di ricerca per il relatore:** una verifica GT-free dei KPI giustifica l'estensione della libreria di regole, oppure e' scientificamente preferibile dichiarare i limiti di osservabilita' e concentrarsi sulla tesi dell'harness?

## 2. Protocollo di audit

- Inventario degli schemi dei file Market (A/1).
- Inventario dei nomi KPI (A/2).
- Profilazione descrittiva delle misure (A/3).
- Riepilogo di fattibilita' per famiglie R03/R04/R05 (A/4).
- Matching per cloudbed, finestra, componente e suffisso KPI (A/5).
- Matching **esatto** al timestamp UNIX in secondi su metriche TCP di nodo e Istio (A/6).
- Tutte le fasi su **4 finestre development gia' osservate (2 per cloudbed)**; nessun ulteriore caso selezionato da A/3 a A/6.
- Scelta finestre controllata contro i casi storici e senza sovrapposizione con evaluation / mixed_quarantine / OOD holdout secondo il protocollo di selezione.
- Nessuna lettura di \`record.csv\`, \`query.csv\`, etichette di causa o risposte Gemini. A/6 rilegge \`Market.zip\`, ma solo \`metric_node.csv\` e \`metric_mesh.csv\` per finestre development selezionate. Non sono stati eseguiti test di accuracy.

Gli script e i test offline sono in \`src/evaluation/network_*.py\` e \`src/tests/test_network_*.py\` del branch indicato. Ogni report contiene hash di provenienza e/o controlli di coerenza sugli artifact precedenti.

## 3. Evidenze osservate

### R03 — TCP retransmission

Metriche di nodo: \`system.net.tcp.retrans_segs\`, \`system.tcp.retrans_pct\`, con contesto \`system.net.tcp.in_segs\` e \`system.net.tcp.out_segs\`.

- A/5: 24/24 profili nodo-finestra con le due metriche e con il contesto TCP disponibili.
- A/6: **720/720** coppie numeriche allo stesso timestamp e nodo; il contesto TCP e' disponibile in tutti i 720 timestamp.
- **274** coppie entrambe positive; **116** con solo \`retrans_segs\` positivo; **146** con solo \`retrans_pct\` positivo; **184** con nessuna delle due positiva.
- A/3: \`retrans_segs\` presenta valori decrescenti in tutti i 24 profili: non si comporta come un puro contatore cumulativo monotono nei campioni letti. Unita' e trasformazioni del KPI non ancora verificate.

**Limite:** metriche a livello **nodo**, non container. Anche co-positivita' allo stesso istante non permette di attribuire una ritrasmissione a un container o stabilire una root cause.

**Decisione proposta:** non implementare R03 come diagnosi deterministica di container; eventualmente valutare un indizio *node-level* esplicitamente non causale.

### R04 — Packet corruption

A/4 su valori gia' profilati:

- \`container_network_{receive,transmit}_errors.eth0\`: **336/336** profili tutti zero.
- \`container_network_{receive,transmit}_packets_dropped.eth0\`: **336/336** profili tutti zero.
- \`system.net.packets_{in,out}.error\`: **48/48** profili tutti zero.
- Totale **720/720** profili tutti zero nelle quattro finestre osservate.

**Limite:** anche un errore RX/TX o un drop positivo non sarebbe prova specifica di *packet corruption*. L'assenza di variazione nel campione non dimostra che i KPI siano sempre zero in tutto Market.

**Decisione proposta:** sospendere R04; non costruire soglie arbitrarie o affermare di aver diagnosticato corruzione di pacchetti.

### R05 — Network latency

Metriche Istio: \`istio_request_duration_milliseconds.*\` abbinate a \`istio_requests.*\` con identico suffisso, su stesso componente e finestra.

- A/5: **1.132/1.132** coppie di profili per componente/suffisso; 566 coppie con entrambi i massimi positivi.
- A/6: **33.960/33.960** coppie numeriche allo stesso timestamp, componente e suffisso KPI.
- **14.679** coppie entrambe positive; **16.719** entrambe non positive; **2.558** solo richieste positive; **4** solo durata positiva.

**Limite:** durata RPC applicativa != tempo di propagazione/trasmissione di rete. Manca una verifica della semantica e un'analisi causale dei trace. Le coppie disallineate in positivita' non provano un errore nei dati.

**Decisione proposta:** R05 e' candidata a un eventuale studio *successivo* su ritardi delle richieste e trace; non puo' essere chiamata oggi una regola di *network latency*.

## 4. Cosa significa scientificamente

La distinzione fondamentale e' tra:

1. **Osservabilita'**: il KPI esiste e fornisce numeri;
2. **allineamento**: due KPI si possono confrontare nella stessa finestra e allo stesso timestamp;
3. **semantica**: misura nota, unita' note, interpretazione dei contatori/rate/aggregazioni;
4. **attribuzione**: identificazione del componente e della causa del guasto;
5. **validazione**: prestazioni del detector su casi appropriati, senza leakage.

Le fasi A/1–A/6 documentano soprattutto i punti 1 e 2, non dimostrano i punti 3–5. Nessuna delle nuove regole R03–R05 e' stata implementata o validata.

## 5. Proposta per la discussione

**Scelta raccomandata per rispettare la scadenza della tesi:** congelare le otto regole gia' disponibili, includere il *negative result* R04 come limite osservativo, documentare R03 come proxy node-level e R05 come opportunita' di estensione non ancora provata. Evitare nuove ablation finche' obiettivo e protocollo non siano concordati col relatore.

Questioni da concordare:

1. Il contributo centrale della tesi e' il **processo di harnessing** con regole GT-free e verifica, oppure la copertura esaustiva delle classi di guasto?
2. E' accettabile e scientificamente informativo riportare esplicitamente **tre regole non validate**, motivandone i limiti empirici?
3. E' sensato fare un piccolo esperimento *pre-registrato* su R05 con \`trace_span.csv\`, mantenendo separati sviluppo e valutazione, oppure e' meglio fermarsi?
4. E' opportuno discutere il *potenziale* trasferimento di conoscenza nell'harness (proposta/raffinamento di nuove regole), **senza affermare che sia gia' dimostrato**?
5. Quali analisi sono essenziali prima del 1 dicembre e quali dovrebbero essere dichiarate lavoro futuro?

## 6. Riproducibilita' e confini

Artefatti locali Colab attesi:

- \`/content/network_kpi_inventory_v1.json\`
- \`/content/network_signal_profile_v1.json\`
- \`/content/network_feasibility_summary_v1.json\`
- \`/content/network_signal_pairing_v1.json\`
- \`/content/network_temporal_alignment_v1.json\`

Gli output possono essere riprodotti dai moduli A/2–A/6 sullo stesso Market ZIP, split e manifest GT-free, rispettando gli hash dei file e il seed della selezione. Conservare i JSON originali, senza modificarli dopo il calcolo, consente di ricostruire la filiera di provenienza.

**Nessuna modifica ai detector baseline, al benchmark scoring, al frozen commit o a evaluation/OOD holdout in questa nota.**
