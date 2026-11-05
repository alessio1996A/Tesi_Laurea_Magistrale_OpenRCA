# Fase 2: integrazione Claude per ablation cross-model OpenRCA

**Stato: sola integrazione provider e test offline. Zero run Claude
effettuate, nessun piano di campagna pagata autorizzato.**

## Provenienza, isolamento e invarianti

- Base: feature/harness-v2-clean-2026-11-03 al commit
  1cdd223e74baa9d48ba057b5d5c719acd915d989.
- Nuovo branch: feature/claude-cross-model-2026-11-05.
- Non usare il branch Gemini 5+1 per questa campagna;
  il suo piano su Drive e' associato a 601007dd95fff29e0d019e47fe0867ccabf3221c,
  e include un primo tentativo 503 da preservare.
- Mantenere invariati: src/agent/prompts.py, cinque tool,
  otto regole, task-aware output contract e scorer ufficiale.
- La model factory usa ANTHROPIC_API_KEY esclusivamente dal runtime;
  nessuna chiave nel codice, su GitHub o negli output.
- Modelli API: claude-sonnet-5-5 e claude-haiku-5-5.
- ChatAnthropic usa max_retries=0: nessun retry automatico
  alla singola richiesta del provider.
- Non impostare temperature, top_p o top_k sui modelli Claude 5.5.

## Fase offline PyCharm (prima di Colab)

Dopo avere controllato git status e preservato eventuali file modificati:

~~~powershell
git fetch origin
git switch --track origin/feature/claude-cross-model-2026-11-05
$env:PYTHONPATH="src"
python -m pip install -r requirements.txt
python -m unittest discover -s src/tests -p "test_anthropic_model_factory.py" -v
python -m unittest discover -s src/tests -p "test_*.py" -v
~~~

I test fake non richiedono chiave Anthropic.

## Colab Secrets: configurazione senza costi

1. Aprire il notebook relativo alla campagna Claude (da preparare
   DOPO i test), e abilitare l'accesso ai Secrets in Colab.
2. Nel pannello con l'icona chiave, premere **Add new secret**.
3. Nome esatto: ANTHROPIC_API_KEY.
4. Valore: chiave del professore, NON da pubblicare o inviare in chat.
5. Abilitare l'accesso del notebook al Secret.
6. La seguente cella e' solo verifica locale, zero chiamate API.

~~~python
import os
from google.colab import userdata
secret = userdata.get("ANTHROPIC_API_KEY")
assert secret and secret.strip(), "Secret ANTHROPIC_API_KEY assente"
os.environ["ANTHROPIC_API_KEY"] = secret
del secret
print("Secret Claude disponibile: SI (valore non mostrato)")
~~~

Una chiave presente non prova ancora l'autorizzazione ai modelli,
la disponibilita' di credito o la validita' della key. Verificarle con
uno smoke test a pagamento solo dopo approvazione esplicita.

## Studio di sviluppo prima dell'incontro col relatore

**Decisione del 5 novembre 2026:** includere tutte le cinque varianti,
compresa A1_PAVE. Gli 8 incidenti sono quelli development congelati V3.

- 8 incidenti x 5 varianti x Sonnet 5.5 = **40 run Sonnet**.
- 8 incidenti x 5 varianti x Haiku 5.5 = **40 run Haiku**.
- Totale: **80 nuove run Claude**, su un nuovo piano create-only.
- Le 40 run Gemini V3 restano una campagna storica separata:
  120 run registrate complessivamente, non 120 casi indipendenti.

I due planner A1_8R_Planning e A1_PAVE mantengono **4+2**.
Non si mescola la configurazione Gemini 5+1 (rimasta in pausa e con un
503 tracciato) alla campagna Claude. Gli altri tre agenti non hanno
planner; budget massimo tool condiviso = 6. Stesso task contract V2.

Il modulo dedicato e' src/evaluation/claude_development_campaign.py.
Costruisce il piano da quello V3 congelato e controlla SHA/source cases,
split e manifest GT-free, senza leggere score o predizioni V3.
La campagna e' organizzata prima su Sonnet (40), poi Haiku (40).
Avvio batch al massimo 8 **nuove run** per chiamata, sequenziali,
con verifica di claim, output JSON e SHA-256 dopo ogni tentativo.
Un errore provider interrompe il batch senza retry automatico.
Un successivo avvio salta le run gia' completate.

Prima delle API:
1. Verificare nel notebook di preflight la suite offline completa.
2. Calcolare costo storico usando esclusivamente contatori token V3.
3. Congelare su Drive il piano di 80 run in create-only.
4. Verificare il Secret ANTHROPIC_API_KEY senza mostrarne il contenuto.
5. Ottenere una conferma esplicita del preventivo e del primo smoke test.
6. Solo dopo il primo smoke, autorizzare la campagna per blocchi.

## Valutazione con lo scorer ufficiale (solo dopo freeze)

Il calcolo di score, partial e exact usa i file ufficiali OpenRCA
(query.csv e ground truth) **solo in una procedura separata, offline,
dopo aver congelato i 40 output del singolo modello (Sonnet prima,
Haiku successivamente)**, usando lo stesso
scorer Microsoft della V3 e lo SHA gia' fissato
2a481ae63cb045c3eadbeca9eddaa10ec1151979.
Non usare query.csv o score per pianificare, scegliere o correggere
le run. Se si valuta Sonnet prima di Haiku, NON modificare la
configurazione o l'ordine delle 40 Haiku gia' preregistrate. Non modificare il JSON dopo scoring. Tenere le run con errori
provider e gli output non conformi nel denominatore/report operativo
e discutere separatamente il loro trattamento nei punteggi.
Misurare accuratezza, exact match, token, latenza e fallimenti;
riportare intervalli di incertezza per 8 casi e limiti della coorte
development gia' conosciuta.

## Ulteriore coorte: solo dopo decisione col relatore

Una valutazione disgiunta su **16 nuovi incidenti Market x 5 varianti
x 2 modelli Claude = 160 nuove run**. Da validare prima con
selezione GT-free, disgiunzione di casi e finestre, stabilita' dei
modelli, disponibilita' del budget. Non rientra nel batch di oggi.
Non assommarla impropriamente ai development per stimare la
generalizzazione.

## Criteri di stop e sicurezza

- Un file di claim prima della chiamata API.
- Un run_id univoco, salvataggio create-only dei risultati e SHA.
- In caso di timeout, 429, 5xx o qualsiasi esito ambiguo:
  registrare errore, mai ritentare automaticamente lo stesso run_id.
- Eseguire lo scoring ufficiale soltanto dopo freeze degli output.
- Analizzare accuratezza, exact match, budget tool usato,
  token, latenza, failure rate e differenza rispetto alla baseline,
  considerando gli effetti del modello e del task.
- Il budget informativo non e' un hard cap della fatturazione.

## Freeze create-only dei 40 risultati Sonnet prima dello scoring

Dopo che tutte le 40 run Sonnet sono state tentate, e senza alcuna run
in stato di integrita' ambiguo, il seguente comando in sola lettura
restituisce una preview del manifest di freeze:

~~~bash
PYTHONPATH=src python -m evaluation.claude_development_freeze \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
  --repo-dir /content/Tesi_OpenRCA_Claude --model sonnet
~~~

Con --write il freeze viene creato in modalita' create-only. Non legge
query.csv, ground truth o scorer. In caso di fallimento 503/429 il
manifest include anche le run con errore provider e non le inventa come
successi; non ripete chiamate. Dopo il freeze si puo' applicare lo
scorer ufficiale OpenRCA **offline** sulle predizioni congelate,
includendo un resoconto di invalidita' e fallimenti infrastrutturali.

Il piano con gli 80 ID rimane immutabile; Haiku si esegue successivamente
senza calibrarla guardando i risultati Sonnet.
