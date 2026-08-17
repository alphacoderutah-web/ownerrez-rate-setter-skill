"""Set base / minimum prices in PriceLabs, through the write guard.

DRY RUN BY DEFAULT. `--execute` must be passed explicitly, and in APPROVE_EXECUTE mode
each change additionally needs a named human approver.

  # show what would change, touch nothing
  python scripts/set_rates.py --unit "Beach House" --base 440

  # actually apply it
  python scripts/set_rates.py --unit "Beach House" --base 440 --execute \
      --reason "pacing 12pp ahead of market at 30 and 60 days" --approved-by Sam

Anything the guard denies is reported with the reason and skipped. A denial is not an
error in this tool -- it is the guard doing its job.
"""
import sys, argparse, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import guard as G
import pricelabs as PL
import properties as P


def main():
    ap = argparse.ArgumentParser(description="Set base/min in PriceLabs, via the write guard.")
    ap.add_argument("--unit", required=True, help="property name as it appears in OwnerRez")
    ap.add_argument("--base", type=float, help="new base price")
    ap.add_argument("--min", dest="min_price", type=float, help="new minimum price")
    ap.add_argument("--reason", default="", help="why this change is being made (audited)")
    ap.add_argument("--execute", action="store_true",
                    help="actually apply. Without this the tool only shows the diff.")
    ap.add_argument("--approved-by", help="name of the human approving")
    ap.add_argument("--override-caps", action="store_true",
                    help="approve a change that exceeds the caps. Requires --approved-by.")
    ap.add_argument("--yes", action="store_true",
                    help="skip the interactive confirmation (non-interactive runs)")
    args = ap.parse_args()

    if args.base is None and args.min_price is None:
        raise SystemExit("nothing to do: pass --base and/or --min")

    try:
        rec = P.resolve(args.unit)
    except C.ConfigError as e:
        raise SystemExit(str(e))

    account, listing_id, pms = rec["account"], rec["pricelabs_id"], rec.get("pms", "ownerrez")
    unit = rec["ownerrez_name"]

    try:
        live = PL.find_listing(account, listing_id)
    except PL.PriceLabsError as e:
        raise SystemExit(f"could not read the listing: {e}")

    print(f"unit        : {unit}")
    print(f"account     : {account}   PriceLabs listing {listing_id} ({pms})")
    print(f"live now    : base={live.get('base')} min={live.get('min')} "
          f"max={live.get('max')} push_enabled={live.get('push_enabled')}")
    try:
        print(f"mode        : {G.current_mode(unit)}  (global {G.current_mode()})")
    except (G.GuardError, C.ConfigError) as e:
        raise SystemExit(f"guard cannot determine mode, refusing to continue: {e}")
    if G.kill_switch_active():
        raise SystemExit(f"KILL SWITCH ACTIVE ({G.kill_switch()}) - refusing to continue")

    changes = []
    if args.base is not None:
        changes.append(("base", PL._num(live.get("base")), args.base))
    if args.min_price is not None:
        changes.append(("min", PL._num(live.get("min")), args.min_price))

    print("\nproposed:")
    for f, cur, new in changes:
        pct = ((new / cur - 1) * 100) if cur else 0
        print(f"  {unit}.{f}: {cur} -> {new} ({pct:+.1f}%)")

    # ---- dry run ------------------------------------------------------------------
    if not args.execute:
        print("\nDRY RUN - nothing will be written. Guard verdict for each change:\n")
        for f, cur, new in changes:
            d = G.check_write(unit, f, cur, new, args.reason)
            print(f"  [{'WOULD APPLY' if d.allowed else 'DENIED'}] {unit}.{f}: {cur} -> {new}")
            for r in d.reasons:
                print(f"      {r}")
        print("\nre-run with --execute to apply.")
        return 0

    # ---- execute ------------------------------------------------------------------
    mode = G.current_mode(unit)
    approvals = {}
    if mode == "APPROVE_EXECUTE" or args.override_caps:
        if not args.approved_by:
            raise SystemExit(f"mode is {mode} - --approved-by is required to apply a change")
        if not args.yes:
            print(f"\nApproving as {args.approved_by}"
                  + ("  (INCLUDING a cap override)" if args.override_caps else ""))
            for f, cur, new in changes:
                print(f"  {unit}.{f}: {cur} -> {new}")
            if input("\ntype the unit name to confirm: ").strip() != unit:
                raise SystemExit("confirmation did not match - aborted, nothing written")
        now = datetime.datetime.now().isoformat(timespec="seconds")
        for f, cur, new in changes:
            approvals[f] = G.Approval(unit=unit, field_name=f, current=cur, proposed=new,
                                      approved_by=args.approved_by, approved_at=now,
                                      override_caps=args.override_caps)

    run_id = f"set_rates-{datetime.date.today()}"
    decisions, to_push = {}, {}
    for f, cur, new in changes:
        d = G.check_write(unit, f, cur, new, args.reason, run_id, approvals.get(f))
        decisions[f] = (d, cur, new)
        if d.allowed:
            to_push[f] = new

    if not to_push:
        print()
        for f, (d, cur, new) in decisions.items():
            print(f"  [NOT APPLIED] {unit}.{f}: {cur} -> {new}")
            for r in d.reasons:
                print(f"      {r}")
        print("\nNothing was written.")
        return 1

    # One POST carries every allowed field, so base and min move together.
    try:
        PL.push_price(account, listing_id, pms,
                      base=to_push.get("base"), min_price=to_push.get("min"))
        pushed_ok, err = True, ""
    except PL.PriceLabsError as e:
        pushed_ok, err = False, str(e)

    print()
    for f, (d, cur, new) in decisions.items():
        if not d.allowed:
            print(f"  [NOT APPLIED] {unit}.{f}: {cur} -> {new}")
            for r in d.reasons:
                print(f"      {r}")
        elif not pushed_ok:
            G.record_applied(d, result="failed", detail=err[:200])
            print(f"  [FAILED] {unit}.{f}: {cur} -> {new}\n      {err[:160]}")
        else:
            G.record_applied(d, result="ok")
            print(f"  [APPLIED] {unit}.{f}: {cur} -> {new}")

    if not pushed_ok:
        return 2

    # A 200 is not proof. Read it back.
    print("\nverifying against PriceLabs...")
    problems = PL.verify(account, [(listing_id, f, v) for f, v in to_push.items()])
    if problems:
        for p in problems:
            print(f"  MISMATCH: {p}")
        print("\nThe write reported success but the read-back disagrees. Investigate "
              "before making further changes.")
        return 2
    print("  all applied changes confirmed live.")
    print("\nRemember to press Sync Now in PriceLabs, or changes can take about a day to "
          "reach the channels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
