# Foglio di rilettura per Alessio (12 testi, senza modello, harness né incidente)

Come si fa. Per ogni testo assegna 0 o 1 a ciascun criterio, **senza aprire** i file `RQ2_RILETTURA_CIECA_CHIAVE_*` e
`RQ2_PUNTEGGI_D_*` (se esistono nel repository) finche' non hai finito. Applica le definizioni cosi' come sono scritte;
se un criterio e' ambiguo scrivi "?" e una riga di nota, non decidere tu a posteriori.

- C1 nomina un tipo di guasto (anche con parole proprie; un sintomo come "latenza alta" da solo vale 0);
- C2 cita un segnale concreto (nome di una metrica o di un componente);
- C3 spiega perche' quel segnale indica quel guasto (c'e' un'osservazione E un'inferenza);
- C4 indica quando (un orario, un timestamp o un intervallo nel testo; "all'inizio della finestra" vale 0);
- C5 dichiara incertezza o cio' che manca (es. "probabilmente", "non confermato").

Testi (campione estratto con seme 17112026, 3 per incidente, solo testi non vuoti, ordine mescolato):

**T01.** high iowait and disk/io saturation

**T02.** high latency in GetProduct requests due to internal processing delay

**T03.** container CPU load (CPU saturation and CFS throttling in adservice2-0 on node-6)

**T04.** Memory exhaustion in the cartservice-0 container (container memory load). Its memory usage was about 237 MB of the 256 MB limit at the start of the window. GetCart and AddItem calls on cartservice-0 then took 15–19 s, and these delays propagated to the frontend and checkoutservice. At about 1647760080 the container restarted, probably an OOM kill, and its memory dropped to about 44 MB.

**T05.** node disk write I/O burst with a transient disk space spike (iowait, io.util and disk.used rise sharply on node-5)

**T06.** NullPointerException in AdService.java

**T07.** Broken connections between productcatalogservice and the TiDB database, with a probable network-level fault on that path. productcatalogservice-1 and -2 logged repeated 'mysql packets.go:37: unexpected EOF' and 'driver: bad connection' errors around 1647821906–1647821966. Two GetProduct spans lasted about 89–155 s around 1647821876. All three productcatalogservice replicas showed a simultaneous dip in CPU and network traffic at 1647821940. Frontend request durations to productcatalogservice rose from 1647822120. The evidence does not confirm a specific fault type, and TiDB container metrics were unavailable.

**T08.** degraded success rate and performance anomaly in adservice

**T09.** node CPU spike (node-6 CPU load)

**T10.** CPU throttling of the cartservice-0 container: the CFS quota (0.6 CPU) was exhausted, causing CPU-starved request processing and multi-second gRPC latency in CartService GetCart/AddItem calls

**T11.** Container memory exhaustion in cartservice-0 (abrupt RSS and working-set surge with a page-fault spike, likely a memory leak or unbounded allocation), causing CPU throttling and gRPC latency

**T12.** NullPointerException in AdService.java

## Tabella da compilare

| Testo | C1 | C2 | C3 | C4 | C5 | Note |
|---|---|---|---|---|---|---|
| T01 | | | | | | |
| T02 | | | | | | |
| T03 | | | | | | |
| T04 | | | | | | |
| T05 | | | | | | |
| T06 | | | | | | |
| T07 | | | | | | |
| T08 | | | | | | |
| T09 | | | | | | |
| T10 | | | | | | |
| T11 | | | | | | |
| T12 | | | | | | |
