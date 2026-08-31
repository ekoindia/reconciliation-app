"""
GUARD: no real Eko data may enter this repository. Both remotes are PUBLIC.

Real production identifiers have leaked in three separate ways — bank account numbers copied
into fixtures, live SBI KO (agent) IDs used as test data, and a real bank-narration account
fragment. CI's secret scanner cannot catch any of these: it matches credential FORMATS
(keys/tokens), not business identifiers. This test is that missing gate.

Fixtures must use SYNTHETIC values. Conventions already in the suite:
  * accounts .... "ACC-1", "ACC-BANK-1", 112233445566
  * SBI KO ids .. 1A9990xx   (the live estate is 1A85xxxx — 1A999xxx is reserved for tests)
  * de-id ....... 9876543210123 / "Rajesh Kumar"  (deliberately fake, and asserted-masked)

If this test fails, do NOT relax the pattern — replace the value with a synthetic one.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_SUFFIXES = {".py", ".md", ".json", ".jsx", ".js", ".yml", ".yaml", ".txt", ".sh", ".bat"}

# Real production shapes that must never be committed.
FORBIDDEN = [
    # Live SBI KO/agent ids are 1A85xxxx. Tests must use the reserved 1A999xxx range.
    (re.compile(r"\b1A85\d{4,6}\b"), "live SBI KO id (use 1A9990xx instead)"),
    # The production host.
    (re.compile(r"\b122\.176\.147\.78\b"), "production server IP"),
]


def _tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    return [ROOT / f for f in out.split("\n") if f.strip()]


def test_no_real_eko_identifiers_in_tracked_files():
    offenders = []
    for path in _tracked_files():
        if path.suffix.lower() not in SCAN_SUFFIXES or not path.exists():
            continue
        if path.name == Path(__file__).name:          # this file documents the patterns
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern, why in FORBIDDEN:
            for m in pattern.finditer(text):
                line = text[: m.start()].count("\n") + 1
                rel = path.relative_to(ROOT).as_posix()
                offenders.append(f"{rel}:{line} — {why}")
    assert not offenders, (
        "Real Eko data found in tracked files (this repo is PUBLIC):\n  "
        + "\n  ".join(offenders)
    )


def test_real_account_registry_is_not_tracked():
    """The live account registry must stay gitignored."""
    out = subprocess.run(["git", "ls-files", "backend/instance/seed_accounts.json"],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert out == "", "backend/instance/seed_accounts.json (REAL accounts) is tracked by git"


def test_account_numbers_from_the_registry_are_not_committed():
    """Cross-check tracked files against the real registry when it is present locally."""
    reg = ROOT / "backend" / "instance" / "seed_accounts.json"
    if not reg.exists():
        return                                        # CI has no registry — nothing to compare
    real = set(re.findall(r"\b\d{9,20}\b", reg.read_text(encoding="utf-8", errors="replace")))
    if not real:
        return
    offenders = []
    for path in _tracked_files():
        if path.suffix.lower() not in SCAN_SUFFIXES or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n in set(re.findall(r"\b\d{9,20}\b", text)) & real:
            offenders.append(f"{path.relative_to(ROOT).as_posix()} — account ending {n[-4:]}")
    assert not offenders, "Real account numbers found in tracked files:\n  " + "\n  ".join(offenders)
