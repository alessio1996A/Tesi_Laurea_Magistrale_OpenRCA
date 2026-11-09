# EVALUATION20 — Relazione per il relatore, 9 novembre 2026
# Eseguire in Google Colab nel runtime gia' predisposto.
# Legge esclusivamente risultati congelati e la baseline ufficiale Microsoft.
# Nessuna API LLM, nessuna modifica delle 900 sorgenti, nessun nuovo esperimento.
# CREA nuovi artefatti con apertura esclusiva (xb); NON rieseguire dopo successo.

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import math
import re
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from random import Random
from statistics import mean
from urllib.request import Request, urlopen

REPO = Path('/content/Tesi_OpenRCA_Evaluation20')
DATA = Path('/content/drive/MyDrive/Tesi_OpenRCA')
SRC = REPO / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.dont_write_bytecode = True

from evaluation import evaluation20_campaign as campaign
from evaluation import evaluation20_preregister as registry
from output.v2_task_contract import enforce_task_output

GIT_COMMIT = 'e4845e7fe9a399e10dd2db6f320dfeaeeddf3379'
PLAN_SHA = 'd390d7acd3db6931c48a64bcd35757ebadf7a7dbdb12b718c1154b45e8757342'
FREEZE_SHA = 'f53effaa81fada14bab31b50ba0983e3642ff818294ac43550587e6982e4ee5f'
INVENTORY_SHA = 'c12257a0ba87502090121c6393182f5f94a22ef08cef8fadbb853c4bb5addd18'
SCORING_SHA = 'd2f7f6495a36c89664cb6cd864bc0f59dd55b4aa18cee29032b1d0c81748d780'
SCORER_COMMIT = '2a481ae63cb045c3eadbeca9eddaa10ec1151979'
SCORER_SHA = '9a1c235139266c32b0e95c7e9938591b8fe014aad4cde95580f73f13a54d53f1'
SCORER_PATH = Path('/content/OpenRCA_official_scoring_2a481ae63c/main/evaluate.py')
BASELINE_BLOBS = {
    'cloudbed-1': 'b81775fd5ea8e8fca86daf2e2a2fbf4cfc0b8510',
    'cloudbed-2': '080db1b08e2c6d600663da1d5850f4498195ef2c',
}
VARIANTS = ('A0', 'A1', 'A1_8R', 'A1_8R_Planning', 'A1_PAVE')
MODELS = ('sonnet', 'haiku', 'gemini')
CONTRASTS = tuple(zip(VARIANTS[:-1], VARIANTS[1:]))

PLAN_PATH = registry.destination(DATA)
FREEZE_PATH = DATA / 'data/protocols/evaluation20' / (campaign.PROTOCOL + '_execution_freeze_v1.json')
SCORING_PATH = DATA / 'data/results/scoring/evaluation20' / (campaign.PROTOCOL + '_official_raw_scoring_v1.json')
SCORING_SIDECAR = SCORING_PATH.with_suffix('.sha256.json')
MANIFEST_PATH = DATA / 'data/processed/benchmark_inputs_market.csv'
MARKET_PATH = DATA / 'Market.zip'
OUTPUT_DIR = DATA / 'data/reports/relatore_2026-11-09'
FILES = {
    'relazione': OUTPUT_DIR / 'EVALUATION20_RELAZIONE_RELATORE_2026-11-09_v1.md',
    'riepilogo': OUTPUT_DIR / 'EVALUATION20_RIEPILOGO_15_CONFIGURAZIONI_v1.csv',
    'ablazioni': OUTPUT_DIR / 'EVALUATION20_ABLAZIONI_APPAIATE_v1.csv',
    'baseline': OUTPUT_DIR / 'EVALUATION20_BASELINE_MICROSOFT_20_CASI_v1.csv',
    'dettaglio': OUTPUT_DIR / 'EVALUATION20_DETTAGLIO_300_TENTATIVI_v1.csv',
    'integrita': OUTPUT_DIR / 'EVALUATION20_MANIFEST_REPORT_v1.json',
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def assert_equal(actual, expected, what):
    if actual != expected:
        raise RuntimeError(f'STOP {what}: ottenuto {actual!r}, previsto {expected!r}')


def csv_data(items: list[dict], columns: list[str]) -> bytes:
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(items)
    return buffer.getvalue().encode('utf-8-sig')


def clean(text):
    return ' '.join(str(text).split())


def boot(deltas, seed, b=10000):
    rng = Random(seed)
    vals = sorted(mean(rng.choices(deltas, k=len(deltas))) for _ in range(b))
    return vals[int(0.025 * (b - 1))], vals[int(0.975 * (b - 1))]


def f4(value):
    return f'{value:.4f}'


def signed(value):
    return f'{value:+.4f}'


def rows_csv(buf):
    return list(csv.DictReader(io.StringIO(buf.decode('utf-8-sig'), newline='')))


def load_microsoft_archive(cloudbed: str):
    filename = f'agent-Market-{cloudbed}.csv'
    url = (
        'https://raw.githubusercontent.com/microsoft/OpenRCA/' +
        SCORER_COMMIT + '/rca/archive/' + filename
    )
    content = None
    try:
        with urlopen(Request(url, headers={'User-Agent': 'EVALUATION20-thesis-audit'}), timeout=45) as response:
            content = response.read()
        assert_equal(git_blob(content), BASELINE_BLOBS[cloudbed], 'blob archivio Microsoft')
    except Exception as exc:
        content = None
        # Sorgente alternativa solo se i byte coincidono con l'archivio fissato.
        for p in (DATA / filename, DATA / 'data' / filename,
                  Path('/content/OpenRCA_official') / 'rca/archive' / filename,
                  Path('/content/OpenRCA_official_scoring_2a481ae63c') / 'rca/archive' / filename):
            if p.is_file() and git_blob(p.read_bytes()) == BASELINE_BLOBS[cloudbed]:
                content = p.read_bytes()
                print('  Archivio Microsoft verificato da copia locale:', p)
                break
        if content is None:
            raise RuntimeError(f'STOP: impossibile scaricare o trovare archivio verificato {cloudbed}: {exc}') from exc
    rows = rows_csv(content)
    assert_equal(len(rows), 70 if cloudbed == 'cloudbed-1' else 78, 'numero righe archivio')
    assert {'row_id', 'score', 'prediction', 'instruction', 'task_index'} <= set(rows[0]), 'Colonne archivio mancanti'
    indexed = {}
    for row in rows:
        rid = Decimal(row['row_id'])
        assert rid == rid.to_integral_value(), 'row_id non intero'
        ix = int(rid)
        assert ix not in indexed, 'row_id duplicato'
        indexed[ix] = row
    assert_equal(set(indexed), set(range(len(rows))), 'sequenza row_id archivio')
    return indexed, sha_bytes(content)


def main():
    print('=== RELAZIONE RELATORE — EVALUATION20 ===', flush=True)
    if any(p.exists() for p in FILES.values()):
        raise FileExistsError('STOP: report precedente presente. Nessun file sara\u2019 sovrascritto.')
    assert_equal(registry.git_head_clean(REPO), GIT_COMMIT, 'commit Git')
    for p, h, title in ((PLAN_PATH, PLAN_SHA, 'piano'), (FREEZE_PATH, FREEZE_SHA, 'freeze'),
                        (SCORING_PATH, SCORING_SHA, 'scoring'), (SCORER_PATH, SCORER_SHA, 'scorer')):
        assert_equal(sha_path(p), h, title)
    sidecar = json.loads(SCORING_SIDECAR.read_text(encoding='utf-8'))
    assert_equal(sidecar['scoring_report_sha256'], SCORING_SHA, 'sidecar scoring')
    plan = json.loads(PLAN_PATH.read_text(encoding='utf-8'))
    freeze = json.loads(FREEZE_PATH.read_text(encoding='utf-8'))
    report = json.loads(SCORING_PATH.read_text(encoding='utf-8'))
    state = campaign.preflight(DATA, REPO)
    assert_equal(state['counts'], {'MODEL_ERROR_REVIEW_NO_RETRY': 5, 'complete': 295}, 'stati')
    assert len(state['runs']) == 300 and all(not r['issues'] for r in state['runs'])
    assert_equal(freeze['inventory_sha256'], INVENTORY_SHA, 'inventario')
    assert_equal(report['planned_attempts'], 300, 'tentativi')
    assert_equal(report['scored_attempts'], 295, 'score disponibili')
    assert_equal(report['provider_errors_not_scored'], 5, 'errori provider')
    assert_equal(report['prediction_field'], 'raw_response', 'scoring raw')
    assert_equal(report['official_scorer_source_sha256'], SCORER_SHA, 'sorgente scorer report')
    assert_equal(sha_path(MANIFEST_PATH), plan['manifest_sha256'], 'manifest GT-free')
    assert_equal(len(plan['cases']), 20, 'casi piano')
    assert_equal(len(plan['runs']), 300, 'run piano')

    # Controllo indipendente dei 900 artefatti e impronta aggregata.
    inventory = hashlib.sha256()
    for item in sorted(state['runs'], key=lambda r: r['run_id']):
        for kind, path in zip(('claim','result','checksum'), campaign.paths(DATA, item['run_id'])):
            dg = sha_path(path)
            inventory.update(f"{item['run_id']}\t{kind}\t{dg}\n".encode('utf-8'))
    assert_equal(inventory.hexdigest(), INVENTORY_SHA, 'fingerprint dei 900 file')
    print('[1/6] Freeze, scorer, scoring, 900 file verificati: OK', flush=True)

    spec = importlib.util.spec_from_file_location('microsoft_openrca_relazione', SCORER_PATH)
    assert spec and spec.loader
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)

    with MANIFEST_PATH.open('r', encoding='utf-8-sig', newline='') as stream:
        gtfree = {r['case_id']: r for r in csv.DictReader(stream)}
    case_meta = {r['case_id']: r for r in plan['cases']}
    assert_equal(len(case_meta), 20, 'casi distinti')
    import zipfile
    query = {}
    with zipfile.ZipFile(MARKET_PATH, 'r') as package:
        for cb in ('cloudbed-1', 'cloudbed-2'):
            raw = package.read(f'Market/{cb}/query.csv')
            query[cb] = rows_csv(raw)
            assert {'instruction', 'task_index', 'scoring_points'} <= set(query[cb][0])

    archived = {}
    archive_sha = {}
    for cb in ('cloudbed-1', 'cloudbed-2'):
        archived[cb], archive_sha[cb] = load_microsoft_archive(cb)

    base_cases = {}
    baseline_table = []
    for case in plan['cases']:
        cid, cb = case['case_id'], case['cloudbed']
        meta = gtfree[cid]
        qi = int(meta['query_index'])
        original = query[cb][qi]
        old = archived[cb][qi]
        for name, value in (('task manifest', original['task_index']), ('task archive', old['task_index'])):
            assert_equal(value.strip(), case['task_index'], f'{cid} {name}')
        assert_equal(clean(meta['instruction']), clean(original['instruction']), f'{cid} istruzione manifest')
        assert_equal(clean(old['instruction']), clean(original['instruction']), f'{cid} istruzione archivio Microsoft')
        assert original['scoring_points'].strip(), 'ground truth vuoto'
        passed, failed, recalculated = scorer.evaluate(old['prediction'], original['scoring_points'])
        published = float(old['score'])
        if not math.isfinite(published) or abs(recalculated - published) > 0.00501:
            raise RuntimeError(f'STOP: score archivio e funzione ufficiale non coincidono {cid}: {published} vs {recalculated}')
        base_cases[cid] = float(recalculated)
        baseline_table.append({
            'case_id': cid, 'cloudbed': cb, 'query_index': qi, 'task_index': case['task_index'],
            'rca_agent_archived_score': published, 'rca_agent_recomputed_score': float(recalculated),
            'rca_agent_strict': int(recalculated == 1.0),
            'archive_git_blob': BASELINE_BLOBS[cb],
        })
    assert_equal(len(base_cases), 20, '20 score baseline')
    baseline_mean = mean(base_cases.values())
    baseline_strict = sum(v == 1 for v in base_cases.values())
    print('[2/6] Baseline RCA-agent Microsoft: allineamento 20/20, scorer ricalcolato OK')
    print('      Media Microsoft:', f4(baseline_mean), '| Strict:', f'{baseline_strict}/20', flush=True)

    status_by_id = {r['run_id']: r for r in state['runs']}
    indexed = {}
    all_rows = []
    invalid_count, wrapper_only, positive_invalid, strict_invalid = 0, 0, 0, 0
    FENCE = re.compile(r'\s*```(?:json)?[ \t]*\r?\n(?P<body>.*?)\s*```\s*', re.I | re.S)
    for row in report['runs']:
        rid, cid = row['run_id'], row['case_id']
        assert rid in status_by_id and cid in case_meta
        meta = status_by_id[rid]
        for k in ('case_id', 'variant', 'model_key', 'status'):
            assert_equal(row[k], meta[k], f'{rid} {k}')
        _, source_path, _ = campaign.paths(DATA, rid)
        assert_equal(sha_path(source_path), row['source_result_sha256'], f'{rid} result hash')
        src = json.loads(source_path.read_text(encoding='utf-8'))
        key = (row['model_key'], cid, row['variant'])
        assert key not in indexed
        complete = row['status'] == 'complete'
        rec = {
            'run_id': rid, 'case_id': cid, 'cloudbed': case_meta[cid]['cloudbed'],
            'task_index': case_meta[cid]['task_index'], 'model': row['model_key'],
            'harness': row['variant'], 'status': row['status'],
            'official_raw_score': None, 'strict': None, 'contract_v2_valid': None,
            'json_status': src.get('json_status'), 'total_tokens': None,
            'end_to_end_seconds': None, 'rca_agent_same_case_score': base_cases[cid],
            'operational_strict': None, 'result_sha256': row['source_result_sha256'],
        }
        if complete:
            score = row['official_raw_score']
            assert type(score) in (float, int) and math.isfinite(score) and 0 <= score <= 1
            audit = src['output_contract_v2']
            assert type(audit['valid']) is bool
            assert src['metrics']['token_usage_complete'] is True
            assert row['raw_response_sha256'] == sha_bytes(src['raw_response'].encode('utf-8'))
            m = src['metrics']
            rec.update({
                'official_raw_score': float(score), 'strict': int(score == 1.0),
                'contract_v2_valid': int(audit['valid']), 'total_tokens': int(m['total_tokens']),
                'end_to_end_seconds': float(m['end_to_end_seconds']),
                'operational_strict': int(score == 1.0 and audit['valid']),
            })
            if not audit['valid']:
                invalid_count += 1
                positive_invalid += int(score > 0)
                strict_invalid += int(score == 1.0)
                mat = FENCE.fullmatch(src['raw_response'])
                if mat:
                    case = case_meta[cid]
                    _, status, inner_audit = enforce_task_output(
                        mat.group('body'), task_index=case['task_index'],
                        instruction=gtfree[cid]['instruction'],
                        start_unix=int(case['start_unix']), end_unix=int(case['end_unix'])
                    )
                    wrapper_only += int(status == 'valid_json' and inner_audit['valid'] is True)
        else:
            assert_equal(row['status'], 'MODEL_ERROR_REVIEW_NO_RETRY', f'{rid} stato errore')
            assert row['official_raw_score'] is None and src.get('error') is not None
        all_rows.append(rec)
        indexed[key] = rec
    assert_equal(len(indexed), 300, '300 chiavi uniche')
    assert_equal(sum(x['official_raw_score'] is not None for x in all_rows), 295, '295 scoring')
    assert_equal(invalid_count, 80, '80 non conformi')
    assert_equal(wrapper_only, 68, '68 soli wrapper')
    assert_equal(positive_invalid, 27, '27 non conformi con score positivo')
    assert_equal(strict_invalid, 13, '13 non conformi strict')
    print('[3/6] Audit score, 503, conformita\u2019 e wrapper: OK', flush=True)

    # Riepilogo per 15 condizioni, con baseline sugli esatti incidenti disponibili.
    table = []
    for mod in MODELS:
        for variant in VARIANTS:
            group = [r for r in all_rows if r['model'] == mod and r['harness'] == variant]
            good = [r for r in group if r['official_raw_score'] is not None]
            assert_equal(len(group), 20, '20 tentativi per configurazione')
            base_matched = mean(x['rca_agent_same_case_score'] for x in good)
            mean_own = mean(x['official_raw_score'] for x in good)
            diffs = [x['official_raw_score'] - x['rca_agent_same_case_score'] for x in good]
            table.append({
                'model': mod, 'harness': variant, 'attempts': len(group), 'complete': len(good),
                'provider_errors': len(group)-len(good), 'official_mean': mean_own,
                'strict': sum(x['strict'] for x in good),
                'v2_valid': sum(x['contract_v2_valid'] for x in good),
                'operational_strict': sum(x['operational_strict'] for x in good),
                'mean_tokens': mean(x['total_tokens'] for x in good),
                'mean_seconds': mean(x['end_to_end_seconds'] for x in good),
                'rca_agent_matched_mean': base_matched,
                'delta_vs_rca_agent': mean(diffs),
                'wins_vs_rca_agent': sum(d > 1e-12 for d in diffs),
                'ties_vs_rca_agent': sum(abs(d) <= 1e-12 for d in diffs),
                'losses_vs_rca_agent': sum(d < -1e-12 for d in diffs),
            })

    pairs = []
    for mi, mod in enumerate(MODELS):
        for ci, (old, new) in enumerate(CONTRASTS):
            chosen = [(indexed[(mod, cid, old)], indexed[(mod, cid, new)])
                      for cid in sorted(base_cases)
                      if indexed[(mod,cid,old)]['official_raw_score'] is not None
                      and indexed[(mod,cid,new)]['official_raw_score'] is not None]
            diffs = [b['official_raw_score']-a['official_raw_score'] for a,b in chosen]
            lo,hi = boot(diffs, seed=20261108 + 100*mi + ci)
            avg_old_tok = mean(a['total_tokens'] for a,b in chosen)
            avg_new_tok = mean(b['total_tokens'] for a,b in chosen)
            avg_old_sec = mean(a['end_to_end_seconds'] for a,b in chosen)
            avg_new_sec = mean(b['end_to_end_seconds'] for a,b in chosen)
            pairs.append({
                'model': mod, 'old': old, 'new': new, 'matched_n': len(diffs),
                'delta_mean': mean(diffs), 'ci95_low':lo, 'ci95_high':hi,
                'wins':sum(d>1e-12 for d in diffs),
                'ties':sum(abs(d)<=1e-12 for d in diffs),
                'losses':sum(d<-1e-12 for d in diffs),
                'token_change_pct':100*(avg_new_tok/avg_old_tok-1),
                'time_change_pct':100*(avg_new_sec/avg_old_sec-1),
            })

    common_gemini = [cid for cid in sorted(base_cases)
                     if all(indexed[('gemini',cid,v)]['official_raw_score'] is not None for v in VARIANTS)]
    assert_equal(len(common_gemini),16,'Gemini comune')
    print('[4/6] 15 configurazioni, 12 confronti e sottocoorte Gemini: OK', flush=True)

    # Relazione per il professore; il report non espone scoring_points/raw_response.
    md = [
        '# Relazione scientifica EVALUATION20 — incontro con il relatore',
        '', '**Data:** 9 novembre 2026  |  **Scadenza tesi:** 1 dicembre 2026',
        '', '## Domanda di ricerca e progetto',
        '', 'La tesi studia l\'effetto di livelli progressivi di Harness Engineering sulla Root Cause Analysis con LLM,',
        'utilizzando il benchmark Microsoft OpenRCA 1.0. Le configurazioni sono A0 (tool/LLM), A1 (evidenze deterministiche),',
        'A1_8R (otto regole), A1_8R_Planning (esplorazione e verifica) e A1_PAVE (evidenze strutturali-temporali).',
        'A1_PAVE e\u2019 un adattamento sperimentale ispirato a PAVE, non un\u2019implementazione integrale di OpenRCA 2.0.',
        '', '## Disegno, protezioni e stato',
        '', '- Development: 8 incidenti, separati dai dati di valutazione; EVALUATION20 non e\u2019 una replica dei development.',
        '- Evaluation: 20 incidenti (10 per cloudbed), sette task, casi multi-guasto, disgiunzione temporale con coorti protette.',
        '- 20 incidenti x 3 modelli x 5 harness x 1 replica = **300 tentativi**.',
        '- **295 diagnosi complete**; **5 errori provider Gemini 503**, conservati senza retry, con score mancante e non imputato.',
        '- Protocollo preregistrato, commit e 900 artefatti verificati mediante SHA256; scoring eseguito dopo il freeze.',
        '- Metriche primarie: score sul `raw_response` con `evaluate()` originale Microsoft. Il contratto V2 e\u2019 un controllo separato del formato.',
        '', '## Risultati ufficiali e confronto RETROSPETTIVO Microsoft',
        '', f'Baseline Microsoft RCA-agent archiviata, sui **medesimi 20 incidenti**: **score medio {baseline_mean:.4f}**, **strict {baseline_strict}/20**.',
        'I punteggi delle predizioni storiche sono stati ricalcolati con lo scorer ufficiale e allineati ai `query_index` originali.',
        '', '| Modello | Harness | Complete /20 | Score nostro | Strict | V2 valide | Strict e V2 | Baseline su casi disponibili | Delta vs Microsoft |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in table:
        md.append(f"| {r['model']} | {r['harness']} | {r['complete']}/20 | {f4(r['official_mean'])} | {r['strict']} | {r['v2_valid']} | {r['operational_strict']} | {f4(r['rca_agent_matched_mean'])} | {signed(r['delta_vs_rca_agent'])} |")
    md += [
        '', '**ATTENZIONE — Interpretazione della baseline:** il confronto con RCA-agent Microsoft usa gli stessi casi e la stessa',
        'funzione di scoring, ma non lo stesso modello, set di tool, condizioni temporali o budget di esecuzione.',
        'Non e\u2019 un confronto controllato che isoli l\u2019effetto dell\u2019harness. Il risultato non e\u2019 generalizzabile a tutti gli incidenti OpenRCA.',
        'I punteggi Microsoft su 20 casi non vanno confrontati con le percentuali pubblicate sull\u2019intero benchmark.',
        '', '## Studio di ablazione: differenze appaiate per incidente',
        '', 'Differenza positiva: il nuovo harness ha score maggiore. IC bootstrap percentile al 95%, 10.000 ricampionamenti di incidenti, esplorativi e non corretti per confronti multipli.',
        '', '| Modello | Ablazione | Coppie | Delta score | IC95% | W/T/L | Delta token % | Delta tempo % |',
        '|---|---|---:|---:|---|---|---:|---:|',
    ]
    for r in pairs:
        md.append(f"| {r['model']} | {r['old']} -> {r['new']} | {r['matched_n']} | {signed(r['delta_mean'])} | [{signed(r['ci95_low'])}; {signed(r['ci95_high'])}] | {r['wins']}/{r['ties']}/{r['losses']} | {r['token_change_pct']:+.1f}% | {r['time_change_pct']:+.1f}% |")
    md += [
        '', 'Il **confronto primario preregistrato** e\u2019 A1 - A0 entro ciascun modello. Le altre tre ablazioni sono secondarie.',
        'Il dato principale e\u2019 un guadagno positivo per Sonnet; gli intervalli per Haiku e Gemini includono lo zero.',
        'Regole e planning non hanno effetti universalmente positivi; le combinazioni migliori cambiano per modello.',
        '', '## Affidabilita\u2019 del formato e disponibilita\u2019',
        '', f'- Contratto V2: **{295-invalid_count}/295 valide**, **{invalid_count}/295 non conformi**.',
        f'- Tra le non conformi, **{wrapper_only}/{invalid_count}** supererebbero il contratto rimuovendo *solo* un wrapper Markdown completo.',
        f'- **{positive_invalid}** non conformi ricevono score Microsoft > 0; **{strict_invalid}** hanno score 1.0 ma non rispettano V2.',
        '- Queste sono diagnosi NON corrette retroattivamente: lo score ufficiale e\u2019 rimasto quello della risposta originale.',
        '- La metrica esplorativa `strict e V2` indica successo diagnostico e conformita\u2019 simultanei, NON sostituisce lo score Microsoft.',
        '- Gli errori provider 503 sono mancata disponibilita\u2019, non diagnosi errate; nessuna imputazione automatica a zero.',
        '', '## Limiti metodologici',
        '', '1. **N = 20 incidenti**, con una sola replica per modello/harness/incidente: potenza limitata e varianza dell\u2019LLM non misurata.',
        '2. Le 300 run non sono 300 incidenti indipendenti; usare confronti appaiati per caso.',
        '3. Coorte selezionata con criteri GT-free, ma non e\u2019 un campione casuale rappresentativo di tutti gli incidenti.',
        '4. Confronti multipli, intervalli bootstrap esplorativi, molti pareggi; non dichiarare significativita\u2019 confermativa universale.',
        '5. I cinque errori Gemini comportano missing data: non assumere missing completely at random.',
        '6. Confronto con RCA-agent storico non controllato per modello, strumenti, epoca e budget.',
        '7. Percezione di efficienza: token comparabili soprattutto *entro* provider; tempi dipendono anche da infrastruttura e latenza.',
        '8. Il contratto V2 misura struttura e cardinalita\u2019, non correttezza causale; PAVE non dimostra causalita\u2019 certificata.',
        '', '## Domande per il professore (revisione del 9 novembre)',
        '', '1. E\u2019 corretta la formulazione della conclusione primaria: evidenze deterministiche utili su Sonnet, effetti dipendenti dal modello?',
        '2. Presentiamo il confronto con RCA-agent storico come **benchmark contestuale**, non come confronto causale?',
        '3. Le osservazioni OOD (4 classi di guasto non codificate nelle 8 regole) vanno esplorate prima della consegna o come futuro sviluppo?',
        '4. Il possibile knowledge transfer con approvazione umana resta future work, anziche\u2019 essere sviluppato prima della consegna?',
        '', '## Provenienza e riferimenti',
        '', f'- Repository della tesi: https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA (commit `{GIT_COMMIT}`)',
        f'- Scorer e archivio Microsoft: https://github.com/microsoft/OpenRCA/tree/{SCORER_COMMIT}',
        f'- Piano SHA256: `{PLAN_SHA}`',
        f'- Freeze SHA256: `{FREEZE_SHA}`',
        f'- Inventario dei 900 artefatti SHA256: `{INVENTORY_SHA}`',
        f'- Scoring nostro SHA256: `{SCORING_SHA}`',
        f'- Scorer Microsoft SHA256: `{SCORER_SHA}`',
        f"- Archive cloudbed-1: SHA256 `{archive_sha['cloudbed-1']}`; Git blob `{BASELINE_BLOBS['cloudbed-1']}`",
        f"- Archive cloudbed-2: SHA256 `{archive_sha['cloudbed-2']}`; Git blob `{BASELINE_BLOBS['cloudbed-2']}`",
        '', '**Dichiarazione di integrita\u2019:** nessun risultato di inferenza, scoring o freeze e\u2019 stato modificato per produrre questa relazione.',
        '',
    ]
    text_bytes = ('\n'.join(md)).encode('utf-8')
    payloads = {
        'relazione': text_bytes,
        'riepilogo': csv_data(table, list(table[0])),
        'ablazioni': csv_data(pairs, list(pairs[0])),
        'baseline': csv_data(baseline_table, list(baseline_table[0])),
        'dettaglio': csv_data(all_rows, list(all_rows[0])),
    }
    inventory_manifest = {
        'schema': 'evaluation20_professor_report_provenance_v1',
        'source': 'frozen evaluation20 results + exact Microsoft archive',
        'git_commit': GIT_COMMIT, 'plan_sha256': PLAN_SHA,
        'execution_freeze_sha256': FREEZE_SHA, 'inventory_sha256': INVENTORY_SHA,
        'scoring_report_sha256': SCORING_SHA, 'scorer_commit': SCORER_COMMIT,
        'scorer_sha256': SCORER_SHA,
        'microsoft_archive_blob_sha1': BASELINE_BLOBS,
        'microsoft_archive_sha256': archive_sha,
        'baseline_mean_recomputed': baseline_mean,
        'baseline_strict_on_20': baseline_strict,
        'outputs': {FILES[k].name: {'sha256': sha_bytes(v), 'bytes': len(v)} for k,v in payloads.items()},
        'provider_api_calls': 0, 'previous_results_modified': False,
    }
    payloads['integrita'] = (
        json.dumps(inventory_manifest, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n'
    ).encode('utf-8')
    assert all(not path.exists() for path in FILES.values())
    print('[5/6] Relazione e tabelle predisposte (nessuna modifica alle sorgenti): OK', flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for k in ('relazione','riepilogo','ablazioni','baseline','dettaglio','integrita'):
        with FILES[k].open('xb') as stream:
            stream.write(payloads[k])
        assert_equal(sha_path(FILES[k]), sha_bytes(payloads[k]), f'{k} readback')
    assert_equal(sha_path(FREEZE_PATH), FREEZE_SHA, 'freeze dopo scrittura')
    assert_equal(sha_path(SCORING_PATH), SCORING_SHA, 'scoring dopo scrittura')
    print('[6/6] Sei artefatti create-only, readback SHA256: OK', flush=True)
    print('\n=== MATERIALI PER IL PROFESSORE ===')
    for k, p in FILES.items():
        print(f'{k}: {p}')
    print('\nBaseline RCA-agent sullo stesso insieme (score ricalcolati):', f4(baseline_mean),
          '| strict', baseline_strict, '/20')
    print('\nModello     Harness               Nostro   Microsoft matched   Delta  strict')
    for r in table:
        print(f"{r['model']:<11} {r['harness']:<21} {r['official_mean']:.4f}   "
              f"{r['rca_agent_matched_mean']:.4f}             {r['delta_vs_rca_agent']:+.4f}  {r['strict']}")
    print('\n300 tentativi, 295 complete, 5 provider errors | 80 non conformi V2 | 68 wrapper-only')
    print('Nessun retry, nessuna API LLM, nessuna modifica alle 900 sorgenti.')
    print('CODICE USCITA: 0')


if __name__ == '__main__':
    main()