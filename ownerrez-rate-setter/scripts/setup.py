"""First-run setup: config, credential check, property map.

  python scripts/setup.py --init     create .rate-setter/config.json (starts in SHADOW)
  python scripts/setup.py --check    verify credentials reach both APIs
  python scripts/setup.py --map      build/refresh the property map
  python scripts/setup.py --status   show config, mode, caps and map summary

Deliberately starts in SHADOW mode. Writes stay off until you change the mode yourself,
so installing this can never reprice anything.
"""
import sys, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import properties as P


def init(accounts):
    p = C.config_path()
    if p.exists():
        print(f"config already exists at {p} - leaving it alone")
        return 0
    cfg = dict(C.DEFAULT_CONFIG)
    cfg["accounts"] = accounts or ["default"]
    C.save(cfg)
    print(f"created {p}")
    print(json.dumps(cfg, indent=1))
    print("\nMode is SHADOW: everything is read-only until you change it deliberately.")
    print(C.ENV_HELP)
    return 0


def check(cfg):
    accounts = cfg.get("accounts", ["default"])
    print("credential presence (values are never shown):")
    ok = True
    for acct, label, present in C.credential_report(accounts):
        print(f"  {acct:<14} {label:<11} {'SET' if present else 'MISSING'}")
        ok = ok and present
    if not ok:
        print(C.ENV_HELP)
        return 1

    print("\nlive connectivity:")
    import pricelabs as PL
    for acct in accounts:
        try:
            n = len(PL.list_listings(acct))
            print(f"  {acct:<14} PriceLabs   OK ({n} listings)")
        except Exception as e:
            print(f"  {acct:<14} PriceLabs   FAILED: {str(e)[:90]}")
            ok = False
        try:
            props = P._or_get_all(acct, "/v2/properties", {"limit": 100})
            print(f"  {acct:<14} OwnerRez    OK ({len(props)} properties)")
        except Exception as e:
            print(f"  {acct:<14} OwnerRez    FAILED: {str(e)[:90]}")
            ok = False
    return 0 if ok else 1


def build_map(cfg):
    accounts = cfg.get("accounts", ["default"])
    print(f"building property map for: {', '.join(accounts)}")
    m = P.build(accounts)
    P.save(m)
    c = m["counts"]
    print(f"\nsaved {P.map_path()}")
    print(f"  OwnerRez properties : {c['ownerrez_properties']}")
    print(f"  matched to PriceLabs: {c['matched']}")
    print(f"  unmatched           : {c['unmatched']}")
    print(f"  PriceLabs orphans   : {c['pricelabs_orphans']}")
    for label, items in (("UNMATCHED (no PriceLabs listing - cannot be repriced)",
                          m["unmatched"]),
                         ("ORPHANS (PriceLabs listing with no OwnerRez property)",
                          m["pricelabs_orphans"])):
        if items:
            print(f"\n{label}:")
            for i in items:
                print(f"  - {i}")
    return 0


def status(cfg):
    print(f"config     : {C.config_path()}")
    print(f"mode       : {cfg.get('mode')}")
    um = cfg.get("unit_modes") or {}
    if um:
        print("unit modes :")
        for k, v in um.items():
            print(f"             {k}: {v}")
    caps = cfg.get("caps", {})
    print(f"caps       : max change {caps.get('max_change_pct', 0):.0%}, "
          f"{caps.get('max_changes_per_unit_per_week')}/week, "
          f"{caps.get('cooldown_days')}-day cooldown")
    import guard as G
    print(f"kill switch: {'ENGAGED' if G.kill_switch_active() else 'clear'}")
    try:
        m = P.load()
        print(f"map        : {m['counts']['matched']} of "
              f"{m['counts']['ownerrez_properties']} properties matched "
              f"(built {m['built_at'][:16]})")
    except C.ConfigError:
        print("map        : not built yet - run --map")
    applied = [r for r in G.read_audit() if r.get("event") == "applied"]
    print(f"audit      : {len(G.read_audit())} decisions, {len(applied)} applied")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--map", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--accounts", nargs="*",
                    help="account names for multi-account setups, e.g. --accounts florida utah")
    args = ap.parse_args()

    if args.init:
        return init(args.accounts)
    try:
        cfg = C.load()
    except C.ConfigError as e:
        print(e)
        return 1
    if args.check:
        return check(cfg)
    if args.map:
        return build_map(cfg)
    if args.status or not any((args.check, args.map)):
        return status(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
