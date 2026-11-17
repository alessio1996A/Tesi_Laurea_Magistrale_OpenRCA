# -*- coding: utf-8 -*-
"""Genera `docs/MAPPA_CODICE.md`: la mappa dei moduli del progetto, con lo stato del refactoring dei commenti.

Che cosa fa
-----------
Legge l'Appendice A del documento di consolidamento (`docs/CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md`),
che assegna ogni modulo di `src/` a un gruppo (A nucleo, B1/B2 storici in sola conservazione, C1/C2 archiviabili),
e per ogni modulo riporta: righe, scopo (prima riga della docstring del modulo), protezione da hash e stato dei commenti.

Stato dei commenti (misurato, non dichiarato a mano):
  - "bloccato"     il file e' protetto da hash: non si puo' toccare nemmeno un commento;
  - "completo"     nessun commento/docstring probabilmente in inglese e nessuna funzione senza docstring;
  - "da fare"      almeno un commento/docstring in inglese oppure almeno una funzione senza docstring.
La lingua e' stimata con due piccoli elenchi di parole (euristica): puo' sbagliare su testi molto brevi, che
vengono contati a parte come "incerti" e non fanno scattare "da fare".

Uso (dalla radice del progetto)
    python tools/refactoring/genera_mappa_codice.py            # riscrive docs/MAPPA_CODICE.md
    python tools/refactoring/genera_mappa_codice.py --stdout   # stampa soltanto
Sola lettura sul codice: scrive un solo file, la mappa.
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from controlla_solo_commenti import FROZEN_BLOB_SHA1, FROZEN_SHA256  # noqa: E402  (stesso elenco del controllore)

DOC_CONSOLIDAMENTO = "docs/CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md"
USCITA = "docs/MAPPA_CODICE.md"

# Parole molto frequenti in inglese e in italiano, per stimare la lingua di un commento.
PAROLE_EN = set("the of and to in is are for with this that from not be as by on or an it if when only no per its "
                "which has have can does do into than then else all any each was were been must should will".split())
PAROLE_IT = set("il lo la le gli un una di del della dei delle degli da in con per su che non e ed o se quando solo come "
                "piu nel nella sono viene ogni tutti tutte questo questa sul sulla dal dalla alla al ai agli puo ne".split())

# Nomi dei gruppi come compaiono nell'Appendice A (ordine di presentazione).
NOMI_GRUPPI = OrderedDict([
    ("A", "A. Nucleo del codice finale (da mantenere e documentare)"),
    ("B1", "B1. Campagne e audit RQ1 storici (conservare: hanno prodotto risultati citabili)"),
    ("B2", "B2. Audit e preflight in sola lettura (conservare: documentano le decisioni di protocollo)"),
    ("C1", "C1. Script manuali una tantum (candidati all'archivio dopo la consegna)"),
    ("C2", "C2. RQ2 pre-V5: ledger, dispatcher, pilot, sonde, prototipi (candidati all'archivio dopo la consegna)"),
])


def lingua(testo: str) -> str | None:
    """'en', 'it' oppure None se il testo e' troppo breve per decidere."""
    parole = re.findall(r"[a-zàèéìòù']+", testo.lower())
    en = sum(p in PAROLE_EN for p in parole)
    it = sum(p in PAROLE_IT for p in parole)
    if en + it < 2:
        return None
    return "en" if en > it else "it"


def leggi_gruppi(radice: Path) -> OrderedDict:
    """{gruppo: [(sottogruppo, [percorso, ...]), ...]} letto dall'Appendice A del documento di consolidamento."""
    righe = (radice / DOC_CONSOLIDAMENTO).read_text(encoding="utf-8").splitlines()
    inizio = next(i for i, r in enumerate(righe) if r.startswith("## Appendice A"))
    gruppi: OrderedDict = OrderedDict((g, []) for g in NOMI_GRUPPI)
    gruppo, sotto = None, ""
    for riga in righe[inizio:]:
        m = re.match(r"### A\.\d+ .*\(gruppo (A|B1|B2|C1|C2)", riga)
        if m:
            gruppo, sotto = m.group(1), ""
            gruppi[gruppo].append(["", []])
            continue
        m3 = re.match(r"\*\*(.+?)\*\*", riga)
        if m3 and gruppo:
            sotto = m3.group(1)
            gruppi[gruppo].append([sotto, []])
            continue
        m4 = re.match(r"\| `([\w/]+\.py)` \|", riga)
        if m4 and gruppo:
            gruppi[gruppo][-1][1].append(m4.group(1))
    # Si scartano i sottogruppi vuoti creati dal titolo della sezione.
    return OrderedDict((g, [(s, mods) for s, mods in lista if mods]) for g, lista in gruppi.items())


def _docstring_vietata(nodo: ast.AST) -> bool:
    """True per le classi Pydantic (`BaseModel`/`BaseSettings`) e le funzioni `@tool`.

    La loro docstring viene inviata al modello (descrizione dello schema o del tool): non va aggiunta, si documentano con
    commenti `#`, e quindi la sua assenza non conta come "funzione senza docstring".
    """
    def nome(n: ast.AST) -> str:
        if isinstance(n, ast.Call):
            return nome(n.func)
        if isinstance(n, ast.Attribute):
            return n.attr
        return n.id if isinstance(n, ast.Name) else ""

    if isinstance(nodo, ast.ClassDef):
        return any(nome(b) in ("BaseModel", "BaseSettings") for b in nodo.bases)
    if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return any(nome(d) in ("tool", "StructuredTool") for d in nodo.decorator_list)
    return False


def misura(percorso: Path) -> dict:
    """Righe, scopo, blocchi inglesi/incerti e funzioni senza docstring di un modulo."""
    testo = percorso.read_text(encoding="utf-8")
    albero = ast.parse(testo)
    blocchi: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(testo).readline):
        if tok.type == tokenize.COMMENT:
            blocchi.append(tok.string.lstrip("# ").strip())
    senza_doc = 0
    for nodo in ast.walk(albero):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(nodo, clean=False)
            if doc:
                blocchi.append(doc)
            elif not isinstance(nodo, ast.Module) and not _docstring_vietata(nodo):
                senza_doc += 1
    conteggio = Counter(lingua(b) or "?" for b in blocchi)
    doc_modulo = ast.get_docstring(albero) or ""
    scopo = next((r.strip() for r in doc_modulo.splitlines() if r.strip()), "(nessuna docstring di modulo)")
    return {"righe": testo.count("\n") + 1, "scopo": scopo, "en": conteggio["en"], "incerti": conteggio["?"],
            "senza_doc": senza_doc + (0 if doc_modulo else 1)}


def stato(rel: str, m: dict) -> str:
    """Stato dei commenti di un modulo."""
    if rel in FROZEN_SHA256 or rel in FROZEN_BLOB_SHA1:
        return "bloccato"
    return "completo" if m["en"] == 0 and m["senza_doc"] == 0 else "da fare"


def cella(testo: str, massimo: int = 110) -> str:
    """Testo adatto a una cella di tabella Markdown (niente barre verticali, lunghezza limitata)."""
    testo = testo.replace("|", "/").replace("`", "'")
    return testo if len(testo) <= massimo else testo[: massimo - 1].rstrip() + "..."


def costruisci(radice: Path) -> str:
    gruppi = leggi_gruppi(radice)
    src = radice / "src"
    righe: list[str] = []
    totali: dict[str, Counter] = {}
    corpo: list[str] = []
    for g, nome in NOMI_GRUPPI.items():
        corpo += [f"## {nome}", ""]
        totali[g] = Counter()
        for sotto, moduli in gruppi[g]:
            if sotto:
                corpo += [f"**{sotto}**", ""]
            corpo += ["| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |", "|---|---:|---|---|---|"]
            for rel in moduli:
                m = misura(src / rel)
                st = stato(rel, m)
                protez = []
                if rel in FROZEN_SHA256:
                    protez.append("SHA-256 consolidamento")
                if rel in FROZEN_BLOB_SHA1:
                    protez.append("hash git RQ1")
                dettaglio = st if st != "da fare" else f"da fare (EN {m['en']}, senza docstring {m['senza_doc']})"
                corpo.append(f"| `{rel}` | {m['righe']} | {cella(m['scopo'])} | {' + '.join(protez) or '-'} | {dettaglio} |")
                totali[g][st] += 1
                totali[g]["tot"] += 1
            corpo.append("")
    righe += [
        "# Mappa del codice",
        "",
        "Generata da `tools/refactoring/genera_mappa_codice.py` a partire dall'Appendice A del documento di consolidamento",
        "(`" + DOC_CONSOLIDAMENTO + "`). Non modificare a mano: si rigenera con lo stesso comando.",
        "",
        "## Come leggere questa mappa",
        "",
        "- I moduli sono divisi in **gruppi** secondo il grafo degli import dai punti d'ingresso che hanno prodotto i risultati.",
        "  \"Fuori dal nucleo\" significa \"non necessario al codice finale\", **non** \"eliminabile\": i percorsi compaiono nei record,",
        "  negli addendum e negli hash, quindi nessun modulo viene spostato, rinominato o cancellato prima della consegna.",
        "- **Protezione**: alcuni file sono verificati da un hash (SHA-256 del consolidamento, sez. 7.2; hash git dei sorgenti RQ1 in",
        "  `evaluation/rq2_protocol_identity_preflight.py`). Cambiare anche un solo carattere, commenti compresi, fa fallire quei controlli:",
        "  restano com'erano, anche se i loro commenti sono in inglese o in italiano misto.",
        "- **Commenti**: \"completo\" = commenti e docstring in italiano e nessuna funzione senza docstring; \"da fare\" = c'e' ancora",
        "  almeno un blocco probabilmente inglese o una funzione senza docstring (la lingua e' stimata con un'euristica).",
        "  Le classi Pydantic e le funzioni `@tool` non hanno docstring di proposito: la docstring verrebbe inviata al modello.",
        "- Verifica del refactoring: `python tools/refactoring/controlla_solo_commenti.py --base <riferimento git>` dimostra che, rispetto",
        "  al riferimento, sono cambiati solo commenti e docstring (albero sintattico identico) e che nessun file protetto e' stato toccato.",
        "",
        "## Riepilogo",
        "",
        "| Gruppo | Moduli | Bloccati da hash | Commenti completi | Da fare |",
        "|---|---:|---:|---:|---:|",
    ]
    for g, nome in NOMI_GRUPPI.items():
        t = totali[g]
        righe.append(f"| {nome.split('(')[0].strip()} | {t['tot']} | {t['bloccato']} | {t['completo']} | {t['da fare']} |")
    righe += [""] + corpo
    return "\n".join(righe).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genera la mappa del codice (docs/MAPPA_CODICE.md)")
    ap.add_argument("--root", default=".", help="radice del repository (default: cartella corrente)")
    ap.add_argument("--stdout", action="store_true", help="stampa la mappa invece di scriverla")
    args = ap.parse_args(argv)
    radice = Path(args.root).resolve()
    testo = costruisci(radice)
    if args.stdout:
        sys.stdout.write(testo)
    else:
        (radice / USCITA).write_text(testo, encoding="utf-8", newline="\n")
        print(f"scritto {USCITA} ({len(testo.splitlines())} righe)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
