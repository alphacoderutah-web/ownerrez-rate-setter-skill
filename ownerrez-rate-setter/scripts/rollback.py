"""Undo applied rate changes, reconstructed from the audit log.

  python scripts/rollback.py --unit "Beach House"                 # plan only
  python scripts/rollback.py --since 2026-08-17T00:00 --execute --approved-by Sam

Plans by default. Applying still passes through the guard, so this cannot be used as a
side door around caps or the kill switch. `--emergency` clears the cooldown and frequency
caps only -- never the kill switch and never the mode, because a halted system should not
be writing at all.
"""
import sys, argparse, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import guard as G
import pricelabs as PL
import properties as P


def plan(unit=None, run_id=None, since=None):
    applied = [r for r in G.read_audit()
               if r.get("event") == "applied" and r.get("result", "ok") == "ok"]
    if unit:
        applied = [r for r in applied if r.get("unit") == unit]
    if run_id:
        applied = [r for r in applied if r.get("run_id") == run_id]
    if since:
        applied = [r for r in applied if (r.get("applied_at") or "") >= since]

    # Restore the value held BEFORE the earliest change in scope, not a chain of
    # intermediate steps. Sorting newest-first and overwriting lands on the oldest.
    applied.sort(key=lambda r: r.get("applied_at", ""), reverse=True)
    oldest = {}
    for r in applied:
        oldest[(r.get("unit"), r.get("field_name"))] = r
    return [{"unit": u, "field_name": f, "restore_to": r.get("current"),
             "current_is": r.get("proposed"), "applied_at": r.get("applied_at"),
             "run_id": r.get("run_id")}
            for (u, f), r in oldest.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit")
    ap.add_argument("--run-id")
    ap.add_argument("--since")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--emergency", action="store_true",
                    help="bypass cooldown/frequency caps (never the kill switch or mode)")
    ap.add_argument("--approved-by")
    args = ap.parse_args()

    if not (args.unit or args.run_id or args.since):
        ap.error("specify --unit, --run-id, or --since")

    ops = plan(args.unit, args.run_id, args.since)
    if not ops:
        print("nothing to roll back for that selector")
        return 0

    print(f"ROLLBACK PLAN ({len(ops)} operation(s)):\n")
    for o in ops:
        print(f"  {o['unit']}.{o['field_name']}: {o['current_is']} -> {o['restore_to']}"
              f"   (undoing change applied {o['applied_at']})")

    if not args.execute:
        print("\nPlan only. Re-run with --execute to apply.")
        return 0

    if G.kill_switch_active():
        print(f"\nKILL SWITCH ACTIVE ({G.kill_switch()}) - release it first. A halted "
              f"system should not be writing at all, even to restore a prior state.")
        return 2

    needs_approval = args.emergency or any(
        G.current_mode(o["unit"]) == "APPROVE_EXECUTE" for o in ops)
    if needs_approval and not args.approved_by:
        print("\n--approved-by is required: a unit is in APPROVE_EXECUTE mode "
              "(or --emergency was passed).")
        return 2

    print("\nApplying...")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    restored = failed = 0

    # Group by unit so base and min restore in a single push.
    by_unit = {}
    for o in ops:
        by_unit.setdefault(o["unit"], []).append(o)

    for unit, unit_ops in by_unit.items():
        try:
            rec = P.resolve(unit)
        except C.ConfigError as e:
            print(f"  SKIPPED {unit}: {e}")
            failed += len(unit_ops)
            continue

        allowed = {}
        for o in unit_ops:
            approval = None
            if needs_approval:
                approval = G.Approval(unit=unit, field_name=o["field_name"],
                                      current=o["current_is"], proposed=o["restore_to"],
                                      approved_by=args.approved_by, approved_at=now,
                                      override_caps=bool(args.emergency))
            d = G.check_write(unit, o["field_name"], o["current_is"], o["restore_to"],
                              f"rollback of {o['run_id'] or 'a prior change'}",
                              f"rollback-{datetime.date.today()}", approval)
            if d.allowed:
                allowed[o["field_name"]] = (d, o["restore_to"])
            else:
                print(f"  DENIED {unit}.{o['field_name']}: {'; '.join(d.reasons)[:90]}")
                failed += 1

        if not allowed:
            continue
        try:
            PL.push_price(rec["account"], rec["pricelabs_id"], rec.get("pms", "ownerrez"),
                          base=allowed.get("base", (None, None))[1],
                          min_price=allowed.get("min", (None, None))[1])
            problems = PL.verify(rec["account"],
                                 [(rec["pricelabs_id"], f, v) for f, (_, v) in allowed.items()])
            for f, (d, v) in allowed.items():
                if problems:
                    G.record_applied(d, result="failed", detail="; ".join(problems)[:200])
                    print(f"  MISMATCH {unit}.{f}: {problems[0][:80]}")
                    failed += 1
                else:
                    G.record_applied(d, result="ok")
                    print(f"  RESTORED {unit}.{f} -> {v}")
                    restored += 1
        except PL.PriceLabsError as e:
            for f, (d, v) in allowed.items():
                G.record_applied(d, result="failed", detail=str(e)[:200])
            print(f"  FAILED {unit}: {str(e)[:120]}")
            failed += len(allowed)

    print(f"\n{restored} restored, {failed} denied/failed.")
    if restored:
        print("Remember to press Sync Now in PriceLabs.")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
