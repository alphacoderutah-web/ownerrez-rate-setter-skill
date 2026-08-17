"""Configuration and credentials for the rate setter.

Two separate things, deliberately kept apart:

  credentials  live only in environment variables. Never in config, never in the repo.
  config       lives in .rate-setter/config.json next to your project, and is safe to
               read: caps, modes, account names. No secrets.

Everything here fails closed. A missing or unreadable config denies writes rather than
falling back to a default, because a default cap is a cap nobody chose.
"""
from __future__ import annotations
import json, os
from pathlib import Path

CONFIG_DIRNAME = ".rate-setter"
CONFIG_NAME = "config.json"

# Credentials, by environment variable. One account is the common case; add a suffix per
# account when you have several (OWNERREZ_TOKEN_FLORIDA, PRICELABS_KEY_FLORIDA...).
ENV_HELP = """
Required environment variables (never put these in config.json):

  OWNERREZ_USERNAME      your OwnerRez API username
  OWNERREZ_TOKEN         your OwnerRez API access token (starts pt_)
  PRICELABS_KEY          your PriceLabs API key

For multiple accounts, suffix each with the account name in UPPER CASE:

  OWNERREZ_USERNAME_FLORIDA / OWNERREZ_TOKEN_FLORIDA / PRICELABS_KEY_FLORIDA
  OWNERREZ_USERNAME_UTAH    / OWNERREZ_TOKEN_UTAH    / PRICELABS_KEY_UTAH
"""


class ConfigError(Exception):
    """Raised when config or credentials are missing. Callers must treat as deny."""


def project_root(start: Path | None = None) -> Path:
    """Nearest ancestor containing .rate-setter/, else the current directory."""
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / CONFIG_DIRNAME).is_dir():
            return d
    return cur


def config_dir(start: Path | None = None) -> Path:
    return project_root(start) / CONFIG_DIRNAME


def config_path(start: Path | None = None) -> Path:
    return config_dir(start) / CONFIG_NAME


DEFAULT_CONFIG = {
    "accounts": ["default"],
    "mode": "SHADOW",
    "unit_modes": {},
    "caps": {
        "max_change_pct": 0.07,
        "max_changes_per_unit_per_week": 2,
        "cooldown_days": 3,
    },
    "sanity": {"min_price": 20, "max_price": 25000},
    "objective": "RevPAR versus market RevPAR growth",
}


def load(start: Path | None = None) -> dict:
    p = config_path(start)
    if not p.exists():
        raise ConfigError(
            f"no config at {p}. Run:  python scripts/setup.py --init")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise ConfigError(f"config at {p} is unreadable ({e}) - failing closed")
    for key in ("mode", "caps"):
        if key not in cfg:
            raise ConfigError(f"config is missing '{key}' - failing closed")
    caps = cfg["caps"]
    if "max_change_pct" not in caps:
        raise ConfigError("caps.max_change_pct is not set - failing closed")
    return cfg


def save(cfg: dict, start: Path | None = None):
    d = config_dir(start)
    d.mkdir(parents=True, exist_ok=True)
    config_path(start).write_text(json.dumps(cfg, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- credentials

def _env(base: str, account: str | None) -> str | None:
    """Look for the account-suffixed variable first, then the bare one."""
    if account and account.lower() != "default":
        v = os.environ.get(f"{base}_{account.upper()}")
        if v:
            return v
    return os.environ.get(base)


def ownerrez_creds(account: str | None = None):
    u = _env("OWNERREZ_USERNAME", account)
    t = _env("OWNERREZ_TOKEN", account)
    if not (u and t):
        raise ConfigError(
            f"OwnerRez credentials not set for account '{account or 'default'}'.\n{ENV_HELP}")
    return u, t


def pricelabs_key(account: str | None = None) -> str:
    k = _env("PRICELABS_KEY", account)
    if not k:
        raise ConfigError(
            f"PriceLabs key not set for account '{account or 'default'}'.\n{ENV_HELP}")
    return k


def credential_report(accounts: list[str]) -> list[tuple[str, str, bool]]:
    """Presence only, never values - safe to print."""
    out = []
    for acct in accounts:
        for label, fn in (("OwnerRez", lambda a: ownerrez_creds(a)),
                          ("PriceLabs", lambda a: pricelabs_key(a))):
            try:
                fn(acct)
                out.append((acct, label, True))
            except ConfigError:
                out.append((acct, label, False))
    return out
