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

Coorte development: otto incidenti gia' usati V3. Quattro varianti
principali: A0, A1, A1_8R, A1_8R_Planning (budget 4+2, per la
comparabilita' con V3). Su due modelli Claude:

8 incidenti * 4 varianti * 2 modelli = 64 nuove run Claude.

A1_PAVE resta analisi secondaria opzionale: 8 * 1 * 2 = 16
run aggiuntive, totale Claude 80. Le 40 run Gemini V3 pregresse
restano una campagna storica a parte (39/40 formalmente valide);
non vanno sommate alle nuove per sostenere un test indipendente.

Per ridurre l'effort iniziale, smoke test minimo 1 caso per modello
e progressione batch 1 -> 4 -> 8, dopo approvazione del budget.

## Coorte indipendente per una conclusione piu' credibile

Prima selezione GT-free di 16 incidenti Market nuovi, non usati
ne' per sviluppo ne' per calibrare l'harness. Quindi:

16 nuovi incidenti * 4 varianti * 2 Claude = 128 run.

Totale proposto: 64 development + 128 indipendenti = 192 nuove
run Claude (oppure 208 includendo A1_PAVE nello sviluppo).
Aggiungendo le 40 run Gemini V3 storiche si hanno 232 run registrate
complessivamente, ma di coorti/tempi diversi; non sono 232 repliche
indipendenti e non autorizzano percentuali generalizzabili.

Se una terza famiglia di modello (Gemini) torna stabile e si vuole
confrontarla *sugli stessi 16 nuovi incidenti*, aggiungere
16 * 4 = 64 run, portando la nuova coorte cross-model a 192.
Questo NON e' nel piano operativo immediato.

Nessuna run a pagamento prima di preregistrazione indipendente,
dry-run offline, verifica provider e approvazione esplicita del
numero di run e del budget in USD.

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
