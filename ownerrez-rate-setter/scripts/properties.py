"""Property map: the one place unit identity is resolved.

Names repeat across accounts, PriceLabs and OwnerRez use different identifiers, and one
physical home is sometimes listed twice (an Airbnb-only and a Vrbo-only record). Resolving
"the Beach House" by string matching is how the wrong property gets repriced.

So identity is pinned once, into `.rate-setter/property-map.json`, and every tool resolves
through it. Anything that cannot be matched is reported rather than guessed.

Build or refresh it with:  python scripts/setup.py --map
"""
from __future__ import annotations
import base64, json, datetime
import requests

import config as C

OR_BASE = "https://api.ownerrez.com"
TIMEOUT = 60


def map_path():
    return C.config_dir() / "property-map.json"


def _or_headers(account):
    u, t = C.ownerrez_creds(account)
    auth = base64.b64encode(f"{u}:{t}".encode()).decode()
    return {"Authorization": f"Basic {auth}", "User-Agent": "ownerrez-rate-setter/1.0"}


def _or_get_all(account, path, params=None):
    """OwnerRez paginates with next_page_url (snake_case) and caps limit at 100."""
    out, url, first = [], f"{OR_BASE}{path}", True
    while url:
        r = requests.get(url, headers=_or_headers(account),
                         params=params if first else None, timeout=TIMEOUT)
        first = False
        if r.status_code != 200:
            raise RuntimeError(f"OwnerRez {path} -> HTTP {r.status_code}: {r.text[:200]}")
        d = r.json()
        out.extend(d.get("items", []))
        nxt = d.get("next_page_url")
        url = f"{OR_BASE}{nxt}" if nxt else None
    return out


def build(accounts: list[str]) -> dict:
    """Pair OwnerRez properties with PriceLabs listings, per account.

    PriceLabs stores the PMS property id as its own listing id when the PMS is OwnerRez,
    which is what makes an exact join possible. Anything that does not join is surfaced
    rather than force-matched on a similar name.
    """
    import pricelabs as PL

    records, orphans, unmatched = [], [], []
    for account in accounts:
        props = _or_get_all(account, "/v2/properties", {"limit": 100})
        listings = PL.list_listings(account)
        by_id = {str(L.get("id")): L for L in listings}
        seen = set()

        for p in props:
            pid = str(p.get("id"))
            L = by_id.get(pid)
            if L:
                seen.add(pid)
            records.append({
                "account": account,
                "ownerrez_id": pid,
                "ownerrez_name": p.get("name"),
                "active": bool(p.get("active")),
                "pricelabs_id": pid if L else None,
                "pms": (L or {}).get("pms", "ownerrez"),
                "bedrooms": (L or {}).get("no_of_bedrooms"),
                "base": (L or {}).get("base"),
                "min": (L or {}).get("min"),
                "max": (L or {}).get("max"),
                "hidden": bool((L or {}).get("isHidden")),
            })
            if not L and p.get("active"):
                unmatched.append(f"{account}: OwnerRez {pid} ({p.get('name')}) "
                                 f"has no PriceLabs listing")

        for lid, L in by_id.items():
            if lid not in seen:
                orphans.append(f"{account}: PriceLabs {lid} ({L.get('name')}) "
                               f"has no OwnerRez property"
                               + (" [hidden]" if L.get("isHidden") else ""))

    return {
        "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "accounts": accounts,
        "counts": {
            "ownerrez_properties": len(records),
            "matched": sum(1 for r in records if r["pricelabs_id"]),
            "unmatched": len(unmatched),
            "pricelabs_orphans": len(orphans),
        },
        "records": records,
        "unmatched": unmatched,
        "pricelabs_orphans": orphans,
    }


def save(m: dict):
    map_path().parent.mkdir(parents=True, exist_ok=True)
    map_path().write_text(json.dumps(m, indent=1), encoding="utf-8")


def load() -> dict:
    p = map_path()
    if not p.exists():
        raise C.ConfigError(
            f"no property map at {p}. Build it with:  python scripts/setup.py --map")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def resolve(name: str) -> dict:
    """Unit name -> its record. Exact match first, then unambiguous case-insensitive.

    A name matching more than one property raises rather than picking one, because
    silently repricing the wrong home is the failure this whole module exists to prevent.
    """
    m = load()
    recs = m["records"]
    exact = [r for r in recs if (r.get("ownerrez_name") or "") == name]
    if len(exact) == 1:
        return _check(exact[0])

    lowered = name.strip().lower()
    loose = [r for r in recs if (r.get("ownerrez_name") or "").strip().lower() == lowered]
    if len(loose) == 1:
        return _check(loose[0])
    if len(loose) > 1:
        where = ", ".join(f"{r['account']}/{r['ownerrez_id']}" for r in loose)
        raise C.ConfigError(f"'{name}' matches {len(loose)} properties ({where}). "
                            f"Use the exact name, or disambiguate by account.")

    partial = [r for r in recs if lowered in (r.get("ownerrez_name") or "").lower()]
    if len(partial) == 1:
        return _check(partial[0])
    if partial:
        names = ", ".join(repr(r["ownerrez_name"]) for r in partial[:8])
        raise C.ConfigError(f"'{name}' is ambiguous. Did you mean one of: {names}?")
    raise C.ConfigError(f"'{name}' is not in the property map. If it is newly added, "
                        f"rebuild with:  python scripts/setup.py --map")


def _check(rec: dict) -> dict:
    if not rec.get("pricelabs_id"):
        raise C.ConfigError(
            f"'{rec['ownerrez_name']}' has no PriceLabs listing - there is nothing to "
            f"write to. Connect it in PriceLabs first, then rebuild the map.")
    return rec
