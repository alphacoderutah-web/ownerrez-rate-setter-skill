"""PriceLabs API client. The only module here that may issue a mutating call.

Two hazards in this API are worth knowing before you touch it:

1. **The write path IS the read path.** `GET /v1/listings` reads; `POST /v1/listings`
   writes. A typo in the HTTP verb is the difference between listing your portfolio and
   repricing it. The POST lives in exactly one function below so there is one place to
   audit.

2. **Only send the fields you are changing.** PriceLabs treats an omitted field as
   unchanged, but a field sent as null as a clear. Building the payload from the full
   listing object will eventually wipe a minimum you meant to keep.

And one habit: a 200 response is not proof the value stuck. Always read it back.
"""
from __future__ import annotations
import requests

import config as C

BASE = "https://api.pricelabs.co/v1"
TIMEOUT = 60


class PriceLabsError(Exception):
    pass


def _headers(account: str | None) -> dict:
    return {"X-API-Key": C.pricelabs_key(account),
            "User-Agent": "ownerrez-rate-setter/1.0"}


def list_listings(account: str | None = None) -> list:
    r = requests.get(f"{BASE}/listings", headers=_headers(account), timeout=TIMEOUT)
    if r.status_code != 200:
        raise PriceLabsError(f"GET /listings -> HTTP {r.status_code}: {r.text[:200]}")
    d = r.json()
    return d.get("listings", d if isinstance(d, list) else [])


def find_listing(account: str | None, listing_id: str) -> dict:
    for L in list_listings(account):
        if str(L.get("id")) == str(listing_id):
            return L
    raise PriceLabsError(f"listing {listing_id} not found in account '{account or 'default'}'")


def _num(v):
    """PriceLabs returns percentages as strings like '69 %'; prices come back numeric."""
    if v is None or isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace("%", "").replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def push_price(account: str | None, listing_id: str, pms: str,
               base: float | None = None, min_price: float | None = None) -> dict:
    """The ONLY mutating call in this package.

    Sends just the fields being changed, so a base update cannot clear a minimum.
    """
    if base is None and min_price is None:
        raise PriceLabsError("nothing to push: pass base and/or min_price")

    entry: dict = {"id": str(listing_id), "pms": pms}
    if base is not None:
        entry["base"] = float(base)
    if min_price is not None:
        entry["min"] = float(min_price)

    r = requests.post(f"{BASE}/listings", headers=_headers(account),
                      json={"listings": [entry]}, timeout=TIMEOUT)
    if r.status_code not in (200, 201):
        raise PriceLabsError(f"POST /listings -> HTTP {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text[:300]}


def verify(account: str | None, expected: list) -> list:
    """Read back and confirm. `expected` is a list of (listing_id, field, value).

    Returns a list of human-readable mismatches; empty means everything stuck.
    """
    problems = []
    live = {str(L.get("id")): L for L in list_listings(account)}
    for listing_id, fieldname, value in expected:
        L = live.get(str(listing_id))
        if not L:
            problems.append(f"listing {listing_id} vanished from the account after the write")
            continue
        actual = _num(L.get(fieldname))
        if actual is None or abs(float(actual) - float(value)) > 0.01:
            problems.append(
                f"listing {listing_id}.{fieldname}: expected {value}, PriceLabs reports {actual}")
    return problems
