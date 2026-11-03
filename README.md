# OpenRCA — Tesi Magistrale in Ingegneria Informatica

**Harness Engineering per Root Cause Analysis con agenti LLM**  
**Stato:** campagna sperimentale V3 completata e valutata, 3 novembre 2026.

Il progetto studia se il supporto deterministico alla raccolta delle evidenze,
l'applicazione di regole diagnostiche e la pianificazione delle verifiche
migliorino le diagnosi RCA su OpenRCA 1.0 (Market). L'LLM non viene riaddestrato.

## 1. Le cinque varianti dell'agente

I **nomi di presentazione** sono differenti dagli identificativi storici usati
nei JSON e nei protocolli congelati:

| Nome presentazione | ID nei risultati | Descrizione |
| --- | --- | --- |
| **A0** | `A0` | Baseline LangGraph ReAct-style e cinque tool |
| **A1** | `A1_V2` | A0 + evidenze preparate deterministicamente |
| **A1_8R** | `A1` | A1 + otto regole diagnostiche (R01, R02, R06–R11) |
| **A1_8R_Planning** | `A1_VERIFY` | 8 regole + planner e verifiche mirate |
| **A1_PAVE** | `A1_VERIFY_ST` | Planning + contesto strutturale/temporale PAVE-inspired |

**Avvertenza:** `A1_PAVE` è una denominazione sintetica per la presentazione:
la variante non implementa integralmente PAVE e non dimostra causalità.
Le etichette sono centralizzate in `src/agent/variant_names.py`; gli ID interni
non sono cambiati, così i risultati rimangono riproducibili.

## 2. Risultati della campagna V3

Stesso modello e stessa coorte: 8 incidenti development × 5 agenti = 40 run,
**una replica per caso e variante**; 39/40 output conformi al contratto V3.
Lo scorer è quello originale Microsoft OpenRCA, fissato al commit
`2a481ae63cb045c3eadbeca9eddaa10ec1151979`.

| Variante | Score medio OpenRCA | Diagnosi esatte | Token medi | Tempo medio |
| --- | ---: | ---: | ---: | ---: |
| A0 | 0,0000 | 0/8 | 35.286 | 157,84 s |
| A1 | 0,4062 | 2/8 | 48.659 | 170,76 s |
| **A1_8R** | **0,5000** | **3/8** | 48.177 | 191,14 s |
| A1_8R_Planning | 0,4375 | 2/8 | **32.144** | **101,67 s** |
| A1_PAVE | 0,2812 | 1/8 | 36.100 | 109,91 s |

Sintesi: il report deterministico migliora lo score in cinque casi rispetto
ad A0; le regole aggiungono due miglioramenti; il planner diminuisce i costi
computazionali con una lieve perdita di score rispetto a A1_8R; ST non
ha prodotto ulteriori miglioramenti nella coorte osservata.

**Limiti:** otto soli casi development, una replica, copertura delle regole
limitata a otto delle quindici classi di guasto, match testuale esatto per
le motivazioni, assenza di test OOD e verifica causale completa.

## 3. Riproducibilità e isolamento

**Commit originale e immutabile della campagna V3:**

`6747eecc77c1b2fff7d581c7284578b5c574b4f7`

Protocollo: `openrca_harness_v2_five_agents_development_v3`.

- Codice originale: il commit sopra; nessuna modifica retroattiva.
- Dati e 40 predizioni: `Tesi_OpenRCA/data/results/v2/<protocollo>/` su Drive.
- Score ufficiali: `Tesi_OpenRCA/data/results/scoring/v2/<protocollo>/`.
- La ground truth era **esclusa** da tool, report e manifest durante
  le run; è stata consultata soltanto per lo scoring successivo.
- Il protocollo non consente retry automatici delle run già reclamate.
- I nuovi commit su questo branch modificano solo la versione di
  presentazione/manutenzione, **non l'attribuzione storica degli output**.

## 4. Struttura ordinata del progetto

```text
src/
  agent/         Grafi LangGraph, prompt, model factory, cinque tool e alias
  harness/       Evidenze, otto regole, planner e contesto strutturale/temporale
  output/        Contratti e validazione JSON specifica per task
  evaluation/    Configurazione, runner, audit e preregistrazione
  tests/         Test offline di regressione e integrità
docs/            Documentazione attuale e protocolli storici
notebooks/       Istruzioni per la demo su Google Drive
requirements.txt Dipendenze Python
```

Il dataset Market e i risultati non sono nel repository: rimangono su Drive.

## 5. Demo Colab per il relatore

**Notebook:** `Tesi_OpenRCA/demo_relatore/Demo_Relatore_OpenRCA_V3.ipynb`
su Google Drive.

La demo mostra il dataset, i componenti, i KPI, il **replay** delle chiamate ai
tool delle run effettive, le diagnosi e i risultati ufficiali con due grafici.
Non invoca Gemini, non altera il freeze e non presenta il replay come una
nuova esecuzione online.

Vedere anche [notebooks/README.md](notebooks/README.md).

## 6. Sviluppo e test

Ambiente di sviluppo: PyCharm, Google Colab e Google Drive.
Le chiavi API devono rimanere nei Secrets Colab / variabili d'ambiente.

Da root del progetto:

```bash
python -m compileall -q src
PYTHONPATH=src python -m unittest discover -s src/tests -p 'test_*.py' -v
```

Non dichiarare la suite verde senza eseguirla nell'ambiente provvisto
delle dipendenze di `requirements.txt`.

## 7. Documentazione

- [Indice e materiali correnti](docs/INDICE_DOCUMENTAZIONE.md)
- [Architettura, risultati e limiti V3](docs/ARCHITETTURA_E_RISULTATI_V3.md)
- [Piano di pulizia sicura](docs/PULIZIA_CODICE_V3.md)

I documenti datati prima della V3 rimangono consultabili come **storico
dello sviluppo**; possono descrivere protocolli e risultati precedenti.
