"""Claim durevoli e create-only, solo offline, contro le chiamate RQ2 duplicate.

Nessun accesso a provider, agente, API, tetto di costo, scorer o telemetria Market.
Un claim significa "lo stage potrebbe essere iniziato", ma NON e' il permesso di eseguirlo.
Il chiamante deve ottenere a parte un gate indipendente di protocollo/autorizzazione.

Un claim NON viene mai rilasciato per timeout: dopo un arresto di Colab, il
CLAIM_WITHOUT_ARTIFACT ambiguo resta una voce da revisionare a mano. Non cancellare ne'
ritentare automaticamente i claim evita fatturazioni duplicate per errore.

Questo giornale V0 accetta SOLO D/C/K dei 4 casi di discovery; gli stage di test restano
inaccessibili, indipendentemente dai congelamenti MOCK della discovery.

Contenuto
---------
- costanti: cartella dei claim, campi esatti di un claim, autorita' e stati;
- `RQ2ClaimError`: errore "chiamata duplicata, giornale corrotto o fase non autorizzata";
- `_claim_filename`: nome del file di un claim (prefisso piu' SHA-256 dell'ID dello stage);
- `RQ2DiscoveryClaimJournal`: il giornale. `_read_claim` rilegge e verifica un claim,
  `audit_restart` controlla claim e archivio dei risultati, `claim_stage` scrive un nuovo claim.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from evaluation.rq2_dryrun_plan import (
    EXPECTED_MANIFEST_SHA256, EXPECTED_SPLIT_SHA256,
)
from evaluation.rq2_stage_artifact_store import (
    RQ2ArtifactStoreError, RQ2StageArtifactStore,
    _encoded, _create_exclusive, _read_canonical, _sha,
)

VERSION = "rq2_discovery_claim_journal_v0"
# Cartella dei file di claim e campi (esatti) che ogni claim deve avere.
CLAIMS_SUBDIRECTORY = Path("data/rq2/stage_claims_v0")
CLAIM_KEYS = frozenset({
    "journal_version", "stage_id", "case_id", "phase", "stage",
    "logical_model", "harness", "model_id_proposed",
    "plan_preview_sha256", "split_sha256", "manifest_sha256",
    "dependency_record_hashes", "attempt_number", "created_at_utc",
    "authority", "claim_sha256",
})
# Autorita' dichiarata in ogni claim: nessuna. Stati: claim senza risultato (da revisionare a
# mano) e claim con il risultato corrispondente registrato.
AUTHORITY = "NO_API_AUTHORITY"
REVIEW = "CLAIM_WITHOUT_ARTIFACT"
FINISHED = "MATCHING_ARTIFACT_RECORDED"


class RQ2ClaimError(ValueError):
    """Rifiuta chiamate duplicate, giornale corrotto o fase non autorizzata."""


def _claim_filename(stage_id: str) -> str:
    """Nome del file di claim di `stage_id`: `RQ2_CLAIM_` + SHA-256 dell'ID + `.json`."""
    return "RQ2_CLAIM_" + _sha(stage_id.encode("utf-8")) + ".json"


class RQ2DiscoveryClaimJournal:
    """Verifica dei sorgenti in sola lettura; percorso di scrittura fisso, nessun dispatch esterno."""

    def __init__(self, *, data_dir: Path):
        """Apre il giornale su `data_dir`: usa l'archivio degli stage per piano e righe.

        Il costruttore NON crea cartelle, claim, LLM o esperimenti.
        """
        self.store = RQ2StageArtifactStore(data_dir=Path(data_dir))
        self.entries = self.store.entries
        self.plan_sha = self.store.plan_sha
        self.root = self.store.data_dir / CLAIMS_SUBDIRECTORY
        self._guard_directory()

    def _guard_directory(self):
        """Verifica che i percorsi del giornale non siano link e che la cartella sia una cartella."""
        for part in (
            self.store.data_dir / "data/rq2",
            self.root,
        ):
            if part.is_symlink():
                raise RQ2ClaimError("Symlink in claim journal path")
        if self.root.exists() and not self.root.is_dir():
            raise RQ2ClaimError("Claim journal path is not a directory")

    def _entry(self, sid: str) -> dict:
        """Riga del piano per `sid`; solo gli stage di discovery sono ammessi (il test e' vietato)."""
        if type(sid) is not str or sid not in self.entries:
            raise RQ2ClaimError("Unplanned stage ID")
        entry = self.entries[sid]
        if entry["phase"] != "discovery":
            raise RQ2ClaimError("TEST stage claims forbidden before scientific freeze")
        return entry

    def _path(self, sid: str) -> Path:
        """Percorso del file di claim dello stage `sid` (dopo aver verificato che sia ammesso)."""
        self._entry(sid)
        return self.root / _claim_filename(sid)

    def _read_claim(self, sid: str) -> dict | None:
        """Legge e verifica il claim di `sid`; `None` se non esiste.

        Controlli: 1) file canonico e leggibile; 2) campi esatti; 3) hash del claim;
        4) identita' (stage, caso, fase, modello, harness), hash di piano, split e manifest,
        tentativo numero 1, autorita' "nessuna API", data in UTC e dipendenze uguali a quelle
        del piano.
        """
        path = self._path(sid)
        if not path.exists() and not path.is_symlink():
            return None
        try:
            claim = _read_canonical(path)
        except RQ2ArtifactStoreError as exc:
            raise RQ2ClaimError("Unreadable or noncanonical claim") from exc
        if set(claim) != CLAIM_KEYS:
            raise RQ2ClaimError("Claim schema mismatch")
        core = {key: val for key, val in claim.items()
                if key != "claim_sha256"}
        if claim["claim_sha256"] != _sha(_encoded(core)):
            raise RQ2ClaimError("Claim checksum mismatch")
        entry = self.entries[sid]
        if (
            claim["journal_version"] != VERSION
            or claim["stage_id"] != sid
            or claim["case_id"] != entry["case_id"]
            or claim["phase"] != "discovery"
            or claim["stage"] != entry["stage"]
            or claim["logical_model"] != entry["logical_model"]
            or claim["harness"] != entry["harness"]
            or claim["plan_preview_sha256"] != self.plan_sha
            or claim["split_sha256"] != EXPECTED_SPLIT_SHA256
            or claim["manifest_sha256"] != EXPECTED_MANIFEST_SHA256
            or claim["attempt_number"] != 1
            or type(claim["attempt_number"]) is not int
            or claim["authority"] != AUTHORITY
            or type(claim["model_id_proposed"]) is not str
            or entry["logical_model"] not in claim["model_id_proposed"].lower()
            or type(claim["created_at_utc"]) is not str
            or not claim["created_at_utc"].endswith("+00:00")
            or type(claim["dependency_record_hashes"]) is not dict
            or set(claim["dependency_record_hashes"]) != set(entry["dependencies"])
        ):
            raise RQ2ClaimError("Claim identity or original sources mismatch")
        return claim

    def audit_restart(self) -> dict:
        """Ispeziona claim E archivio dei risultati; non riesegue mai in automatico i non risolti.

        Restituisce i conteggi: claim trovati, claim con risultato corrispondente e claim senza
        risultato (da revisionare a mano). Per ogni claim controlla che i record delle
        dipendenze esistano, siano completi, abbiano l'hash dichiarato e lo stesso modello, e che
        il risultato (se c'e') sia dello stesso modello. File estranei o di stage di test
        nella cartella dei claim bloccano.
        """
        self._guard_directory()
        archive = self.store.audit_restart()
        if not self.root.exists():
            return {
                "journal_version": VERSION,
                "claims": 0,
                "finished_with_matching_result": 0,
                "unresolved_manual_review": 0,
                "result_archive_discovery_count":
                    archive["stored_discovery_stages"],
                "can_execute_api": False,
                "can_execute_test": False,
                "automatic_retry_allowed": False,
                "financial_cost_cap": None,
            }
        all_names = {item.name for item in self.root.iterdir()}
        allowed_names = {
            _claim_filename(sid) for sid, entry in self.entries.items()
            if entry["phase"] == "discovery"
        }
        if all_names - allowed_names:
            raise RQ2ClaimError("Foreign or test-stage file in claims directory")
        found, finished, unresolved = 0, 0, 0
        for sid, entry in self.entries.items():
            if entry["phase"] != "discovery":
                continue
            claim = self._read_claim(sid)
            if claim is None:
                continue
            found += 1
            for dep in entry["dependencies"]:
                previous = self.store.load_discovery_stage(stage_id=dep)
                if previous is None or (
                    previous["record_sha256"] !=
                    claim["dependency_record_hashes"][dep]
                ):
                    raise RQ2ClaimError("Claim dependency digest mismatch")
                if previous["status"] != "RECORDED_COMPLETE":
                    raise RQ2ClaimError("Claim after failed dependent stage")
                if previous["model_id_proposed"] != claim["model_id_proposed"]:
                    raise RQ2ClaimError("Claim uses different model than parent")
            result = self.store.load_discovery_stage(stage_id=sid)
            if result is None:
                unresolved += 1
            else:
                if result["model_id_proposed"] != claim["model_id_proposed"]:
                    raise RQ2ClaimError("Claim and result model identity differ")
                finished += 1
        return {
            "journal_version": VERSION,
            "claims": found,
            "finished_with_matching_result": finished,
            "unresolved_manual_review": unresolved,
            "result_archive_discovery_count":
                archive["stored_discovery_stages"],
            "can_execute_api": False,
            "can_execute_test": False,
            "automatic_retry_allowed": False,
            "financial_cost_cap": None,
        }

    def claim_stage(self, *, stage_id: str, model_id_proposed: str) -> dict:
        """Registra il POSSIBILE inizio di una chiamata; non autorizza NULLA.

        Un claim esistente (anche senza risultato) blocca un secondo tentativo.
        Se si chiede C o K, l'artefatto genitore deve essere completo.
        BLOCKED_DEPENDENCY va registrato senza un claim del provider.

        Argomenti (per nome): `stage_id` e `model_id_proposed`. Passi: 1) modello ben formato e
        coerente con quello logico; 2) audit completo; 3) nessun claim ne' risultato esistenti
        per lo stage; 4) dipendenze complete, dello stesso modello, con hash registrato;
        5) verifica dei sorgenti; 6) contenuto del claim, hash, scrittura create-only.
        """
        entry = self._entry(stage_id)
        if (
            type(model_id_proposed) is not str
            or not model_id_proposed.strip()
            or len(model_id_proposed) > 160
            or entry["logical_model"] not in model_id_proposed.lower()
        ):
            raise RQ2ClaimError("Bad proposed model identity")
        # 2-3. Audit completo; un claim o un risultato esistenti bloccano ogni ritento.
        self.audit_restart()
        if self._read_claim(stage_id) is not None:
            raise RQ2ClaimError("Stage already claimed: NEVER auto retry")
        if self.store.load_discovery_stage(stage_id=stage_id) is not None:
            raise RQ2ClaimError("Stage already recorded: create-only")
        # 4. Ogni dipendenza (D per C, C per K) deve essere completa; se ne registra l'hash.
        dependencies = {}
        for dep in entry["dependencies"]:
            previous = self.store.load_discovery_stage(stage_id=dep)
            if previous is None:
                raise RQ2ClaimError("Cannot claim before dependency result")
            if previous["status"] != "RECORDED_COMPLETE":
                raise RQ2ClaimError("Dependent stage failed; record BLOCKED instead")
            if previous["model_id_proposed"] != model_id_proposed:
                raise RQ2ClaimError("Claim model differs from stored dependency")
            dependencies[dep] = previous["record_sha256"]
        # 5-6. Sorgenti verificati, poi contenuto del claim (senza il suo hash).
        self.store._verify_sources()
        core = {
            "journal_version": VERSION,
            "stage_id": stage_id,
            "case_id": entry["case_id"],
            "phase": entry["phase"],
            "stage": entry["stage"],
            "logical_model": entry["logical_model"],
            "harness": entry["harness"],
            "model_id_proposed": model_id_proposed,
            "plan_preview_sha256": self.plan_sha,
            "split_sha256": EXPECTED_SPLIT_SHA256,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "dependency_record_hashes": dependencies,
            "attempt_number": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "authority": AUTHORITY,
        }
        # Hash del claim, cartella (se serve) e scrittura create-only: se il file esiste, si rifiuta.
        claim = {**core, "claim_sha256": _sha(_encoded(core))}
        self._guard_directory()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            _create_exclusive(self._path(stage_id), _encoded(claim))
        except RQ2ArtifactStoreError as exc:
            raise RQ2ClaimError("Create-only claim refused") from exc
        return {
            "journal_version": VERSION,
            "stage_id": stage_id,
            "claim_sha256": claim["claim_sha256"],
            "status": REVIEW,
            "auto_retry": False,
            "can_execute_api": False,
            "can_execute_test": False,
            "financial_cost_cap": None,
        }
