"""Failure-mode tests for the write guard.

Mostly negative cases on purpose: a guard is only worth having if its refusals are
reliable. Runs entirely against a temporary sandbox, so your real config, audit log and
portfolio are never touched, and no network call is made.

    python scripts/test_guard.py
"""
import sys, json, shutil, tempfile, datetime, importlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


class Sandbox:
    def __init__(self, mode="BOUNDED_AUTONOMY", caps=None, unit_modes=None,
                 corrupt=False, missing=False):
        self.mode, self.corrupt, self.missing = mode, corrupt, missing
        self.caps = caps or {"max_change_pct": 0.07,
                             "max_changes_per_unit_per_week": 2, "cooldown_days": 3}
        self.unit_modes = unit_modes or {}

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rateguard-"))
        import config as C
        importlib.reload(C)
        self.C = C
        cfgdir = self.tmp / C.CONFIG_DIRNAME
        cfgdir.mkdir(parents=True)
        # Pin every path at the sandbox so nothing escapes to the real filesystem.
        C.config_dir = lambda start=None: cfgdir
        C.config_path = lambda start=None: cfgdir / C.CONFIG_NAME
        if not self.missing:
            body = "{ not json" if self.corrupt else json.dumps({
                "accounts": ["default"], "mode": self.mode,
                "unit_modes": self.unit_modes, "caps": self.caps,
                "sanity": {"min_price": 20, "max_price": 25000}})
            (cfgdir / C.CONFIG_NAME).write_text(body, encoding="utf-8")
        import guard as G
        importlib.reload(G)
        G.C = C
        self.G = G
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def applied(self, unit, fld, cur, new, days_ago=0):
        when = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        p = self.G.audit_log()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "applied", "unit": unit, "field_name": fld,
                                "current": cur, "proposed": new,
                                "change_pct": round(new / cur - 1, 4),
                                "applied_at": when.isoformat(timespec="seconds")}) + "\n")


print("=" * 70)
print("RATE SETTER - GUARD FAILURE MODE TESTS")
print("=" * 70)

with Sandbox() as s:
    d = s.G.check_write("Beach House", "base", 400, 425, "pacing ahead")
    check("a legal change is allowed", d.allowed, f"{d.change_pct:+.1%}")

with Sandbox(mode="SHADOW") as s:
    check("SHADOW denies writes", not s.G.check_write("Beach House", "base", 400, 410).allowed)

with Sandbox() as s:
    s.G.engage_kill_switch("test", "unit test")
    check("kill switch denies writes",
          not s.G.check_write("Beach House", "base", 400, 410).allowed)
    s.G.release_kill_switch("test")
    check("releasing the kill switch restores writes",
          s.G.check_write("Beach House", "base", 400, 410).allowed)

with Sandbox() as s:
    d = s.G.check_write("Beach House", "base", 670, 540)     # -19%
    check("oversized change denied", not d.allowed and d.requires_approval,
          f"{d.change_pct:+.1%}")
    check("in-cap change allowed", s.G.check_write("Beach House", "base", 670, 700).allowed)

with Sandbox() as s:
    s.applied("Beach House", "base", 700, 680, days_ago=6)
    s.applied("Beach House", "base", 680, 660, days_ago=5)
    check("frequency cap denied",
          not s.G.check_write("Beach House", "base", 660, 650).allowed)

with Sandbox() as s:
    s.applied("Beach House", "base", 420, 400, days_ago=1)
    check("cooldown denied", not s.G.check_write("Beach House", "base", 400, 395).allowed)

with Sandbox() as s:
    for _ in range(5):
        s.G.check_write("Beach House", "base", 400, 900)      # denied: oversized
    check("denied attempts do not consume the frequency cap",
          s.G.check_write("Beach House", "base", 400, 420).allowed)

with Sandbox() as s:
    check("maximum price is prohibited",
          not s.G.check_write("Beach House", "max", 400, 900).allowed)
    check("unknown lever denied",
          not s.G.check_write("Beach House", "wholesale", 400, 420).allowed)

with Sandbox() as s:
    cases = [("None current", None, 420), ("string proposed", 400, "four hundred"),
             ("zero current", 0, 420), ("negative proposed", 400, -50),
             ("absurdly high", 400, 999999), ("no-op", 400, 400)]
    bad = [lbl for lbl, cur, new in cases
           if s.G.check_write("X", "base", cur, new).allowed]
    check("malformed and absurd values all denied", not bad, f"{len(cases)} cases")

with Sandbox(missing=True) as s:
    check("missing config fails closed", not s.G.check_write("X", "base", 400, 420).allowed)
with Sandbox(corrupt=True) as s:
    check("corrupt config fails closed", not s.G.check_write("X", "base", 400, 420).allowed)

with Sandbox(mode="APPROVE_EXECUTE") as s:
    d = s.G.check_write("Beach House", "base", 400, 415)
    check("APPROVE_EXECUTE requires approval even within caps",
          not d.allowed and d.requires_approval)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    ap = s.G.Approval("Beach House", "base", 400, 415, "Sam", now)
    check("a matching approval allows it",
          s.G.check_write("Beach House", "base", 400, 415, approval=ap).allowed)
    check("an approval for a DIFFERENT value is rejected",
          not s.G.check_write("Beach House", "base", 400, 460, approval=ap).allowed)
    stale = s.G.Approval("Beach House", "base", 400, 415, "Sam",
                         (datetime.datetime.now() - datetime.timedelta(hours=2))
                         .isoformat(timespec="seconds"))
    check("an expired approval is rejected",
          not s.G.check_write("Beach House", "base", 400, 415, approval=stale).allowed)

with Sandbox(mode="BOUNDED_AUTONOMY") as s:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    plain = s.G.Approval("Beach House", "base", 670, 540, "Sam", now)
    check("a plain approval does NOT override the size cap",
          not s.G.check_write("Beach House", "base", 670, 540, approval=plain).allowed)
    override = s.G.Approval("Beach House", "base", 670, 540, "Sam", now, override_caps=True)
    check("an explicit cap override does allow it",
          s.G.check_write("Beach House", "base", 670, 540, approval=override).allowed)

with Sandbox(mode="SHADOW") as s:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    override = s.G.Approval("Beach House", "base", 400, 410, "Sam", now, override_caps=True)
    check("no approval can override SHADOW mode",
          not s.G.check_write("Beach House", "base", 400, 410, approval=override).allowed)

with Sandbox(mode="SHADOW", unit_modes={"Pilot Unit": "BOUNDED_AUTONOMY"}) as s:
    check("a per-unit mode grants authority to just that unit",
          s.G.check_write("Pilot Unit", "base", 400, 420).allowed)
    check("other units stay in the global mode",
          not s.G.check_write("Beach House", "base", 400, 420).allowed)
    check("a near-miss unit name does NOT inherit the override",
          not s.G.check_write("pilot unit", "base", 400, 420).allowed)

with Sandbox() as s:
    s.G.check_write("A", "base", 100, 105)
    s.G.check_write("B", "base", 100, 900)
    events = {r["event"] for r in s.G.read_audit()}
    check("audit records both allowed and denied", {"allowed", "denied"} <= events)
    denied = s.G.check_write("B", "base", 100, 900)
    try:
        s.G.record_applied(denied)
        check("record_applied refuses a denied decision", False, "it did not raise")
    except s.G.GuardError:
        check("record_applied refuses a denied decision", True)

print("\n" + "=" * 70)
passed = sum(1 for _, ok in results if ok)
print(f"GUARD TESTS: {passed}/{len(results)} passed")
print("VERDICT:", "ALL PASSED" if passed == len(results) else "FAILURES PRESENT")
sys.exit(0 if passed == len(results) else 1)
