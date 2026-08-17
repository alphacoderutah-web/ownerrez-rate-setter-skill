"""The write guard: the single choke point every rate change must pass through.

Design principle: FAIL CLOSED. Any uncertainty -- missing config, unparseable mode, a cap
that cannot be evaluated -- denies the write. A guard that fails open is not a guard.

Enforced in order:
  1. Kill switch present        -> deny everything, unconditionally
  2. Mode (global or per-unit)  -> SHADOW denies all writes
  3. Permitted lever            -> base and min only; a maximum price is prohibited
  4. Value sanity               -> non-numeric, non-positive, or absurd values denied
  5. Size cap                   -> a change larger than the cap needs explicit approval
  6. Frequency cap              -> too many changes this week needs explicit approval
  7. Cooldown                   -> a change needs time to show an effect
  8. APPROVE_EXECUTE            -> per-change human approval required

Every decision, allowed or denied, is appended to the audit log. Only changes that were
actually APPLIED count toward the caps, so denied attempts cannot exhaust your budget.
"""
from __future__ import annotations
import json, datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path

import config as C

WRITE_MODES = {"APPROVE_EXECUTE", "BOUNDED_AUTONOMY", "FULL_AUTONOMY"}
# A maximum price caps your own upside and is the most common expensive mistake in
# dynamic pricing. Cap individual dates with an override instead.
ALLOWED_FIELDS = {"base", "min"}


@dataclass
class Approval:
    """Authorisation for ONE exact change. Bound tightly on purpose: approving a routine
    change must never silently authorise a different or larger one."""
    unit: str
    field_name: str
    current: float
    proposed: float
    approved_by: str
    approved_at: str
    override_caps: bool = False

    def matches(self, unit, field_name, current, proposed) -> bool:
        try:
            return (self.unit == unit and self.field_name == field_name
                    and abs(float(self.current) - float(current)) < 1e-6
                    and abs(float(self.proposed) - float(proposed)) < 1e-6)
        except (TypeError, ValueError):
            return False

    def expired(self, minutes: int = 15) -> bool:
        try:
            age = datetime.datetime.now() - datetime.datetime.fromisoformat(self.approved_at)
            return age.total_seconds() > minutes * 60
        except Exception:
            return True


@dataclass
class Decision:
    allowed: bool
    mode: str
    unit: str
    field_name: str
    current: float | None
    proposed: float | None
    change_pct: float | None
    reasons: list = field(default_factory=list)
    requires_approval: bool = False
    checked_at: str = ""
    run_id: str | None = None

    def to_dict(self):
        return asdict(self)


class GuardError(Exception):
    """The guard itself cannot function. Callers must treat as deny."""


def audit_log() -> Path:
    return C.config_dir() / "write-audit.jsonl"


def kill_switch() -> Path:
    return C.config_dir() / "KILL-SWITCH"


def kill_switch_active() -> bool:
    return kill_switch().exists()


def current_mode(unit: str | None = None) -> str:
    """Per-unit mode wins on an exact name match, else the global mode.

    A name that does not match exactly falls back to the global mode, which is the
    restrictive direction -- a typo can never accidentally grant authority.
    """
    cfg = C.load()
    if unit:
        um = cfg.get("unit_modes") or {}
        if unit in um:
            return um[unit]
    mode = cfg.get("mode")
    if not isinstance(mode, str) or not mode:
        raise GuardError("mode is not set in config - failing closed")
    return mode


def caps() -> dict:
    return C.load()["caps"]


def _append(entry: dict):
    p = audit_log()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_audit(limit: int | None = None) -> list:
    p = audit_log()
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:] if limit else rows


def _recent_applied(unit: str, field_name: str, days: int) -> list:
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    return [r for r in read_audit()
            if r.get("event") == "applied"
            and r.get("unit") == unit and r.get("field_name") == field_name
            and (r.get("applied_at") or "") >= cutoff]


def check_write(unit: str, field_name: str, current, proposed,
                reason: str = "", run_id: str | None = None,
                approval: Approval | None = None) -> Decision:
    """Evaluate one proposed change. Never performs the change itself."""
    now = datetime.datetime.now()
    d = Decision(allowed=False, mode="UNKNOWN", unit=unit, field_name=field_name,
                 current=current, proposed=proposed, change_pct=None,
                 checked_at=now.isoformat(timespec="seconds"), run_id=run_id)

    def finish(msg, requires_approval=False):
        d.reasons.append(msg)
        d.requires_approval = requires_approval
        _audit(d, reason)
        return d

    try:
        if kill_switch_active():
            return finish("KILL SWITCH ACTIVE - all writes halted. Delete "
                          f"{kill_switch()} to re-enable, once you know why it engaged.")

        mode = current_mode(unit)
        d.mode = mode
        if mode not in WRITE_MODES:
            return finish(f"mode is {mode} - writes are not permitted in this mode")

        if field_name == "max":
            return finish("setting a maximum price is prohibited - it caps your own upside. "
                          "Cap individual dates with an override instead.")
        if field_name not in ALLOWED_FIELDS:
            return finish(f"field '{field_name}' is not a permitted lever "
                          f"(allowed: {sorted(ALLOWED_FIELDS)})")

        try:
            cur_f, new_f = float(current), float(proposed)
        except (TypeError, ValueError):
            return finish(f"non-numeric values (current={current!r}, proposed={proposed!r})")
        if cur_f <= 0:
            return finish(f"current value {cur_f} is not positive - cannot compute a change")

        sanity = C.load().get("sanity", {})
        lo = sanity.get("min_price", 20)
        hi = sanity.get("max_price", 25000)
        if not (lo <= new_f <= hi):
            return finish(f"proposed {new_f} outside sanity bounds [{lo}, {hi}]")
        if new_f == cur_f:
            return finish("no-op: proposed equals current")

        change = (new_f / cur_f) - 1.0
        d.change_pct = round(change, 4)

        c = caps()
        max_pct = float(c["max_change_pct"])
        max_week = int(c.get("max_changes_per_unit_per_week", 2))
        cooldown = int(c.get("cooldown_days", 3))

        valid_override = (approval is not None and approval.override_caps
                          and approval.matches(unit, field_name, current, proposed)
                          and not approval.expired())

        if not valid_override:
            if abs(change) > max_pct + 1e-9:
                return finish(f"change {change:+.1%} exceeds cap {max_pct:.0%} "
                              f"- requires explicit human approval", True)
            week = _recent_applied(unit, field_name, 7)
            if len(week) >= max_week:
                return finish(f"{len(week)} change(s) already applied to {unit}.{field_name} "
                              f"in the last 7 days (cap {max_week}) - requires approval", True)
            recent = _recent_applied(unit, field_name, cooldown)
            if recent:
                last = max(r.get("applied_at", "") for r in recent)
                return finish(f"cooldown: {unit}.{field_name} changed at {last[:16]}, within "
                              f"the {cooldown}-day cooldown. A change needs time to show an "
                              f"effect before another is layered on top.")

        if mode == "APPROVE_EXECUTE":
            if approval is None:
                return finish("APPROVE_EXECUTE mode - human approval required before "
                              "applying", True)
            if not approval.matches(unit, field_name, current, proposed):
                return finish("approval does not match this exact change - refusing", True)
            if approval.expired():
                return finish("approval has expired - re-approve to continue", True)
            d.reasons.append(f"approved by {approval.approved_by}")

        if valid_override:
            d.reasons.append(f"caps overridden by explicit approval from {approval.approved_by}")

        d.allowed = True
        d.reasons.append(f"within caps ({change:+.1%} of {max_pct:.0%})")
        _audit(d, reason)
        return d

    except (GuardError, C.ConfigError) as e:
        return finish(f"GUARD FAILED CLOSED: {e}")
    except Exception as e:
        return finish(f"GUARD FAILED CLOSED (unexpected): {type(e).__name__}: {e}")


def _audit(d: Decision, reason: str):
    entry = d.to_dict()
    entry["event"] = "allowed" if d.allowed else "denied"
    entry["business_reason"] = reason
    try:
        _append(entry)
    except Exception:
        pass          # never let an audit failure mask the decision itself


def record_applied(d: Decision, result: str = "ok", detail: str = ""):
    """Record that an ALLOWED change was actually applied. Only this counts toward caps."""
    if not d.allowed:
        raise GuardError("record_applied called for a change that was not allowed")
    _append({"event": "applied", "unit": d.unit, "field_name": d.field_name,
             "current": d.current, "proposed": d.proposed, "change_pct": d.change_pct,
             "mode": d.mode, "run_id": d.run_id,
             "applied_at": datetime.datetime.now().isoformat(timespec="seconds"),
             "result": result, "detail": detail})


def engage_kill_switch(who: str, why: str):
    p = kill_switch()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"Engaged {datetime.datetime.now().isoformat(timespec='seconds')}\n"
                 f"by: {who}\nreason: {why}\n\nDelete this file to re-enable writes.\n",
                 encoding="utf-8")
    _append({"event": "kill_switch_engaged", "who": who, "why": why,
             "at": datetime.datetime.now().isoformat(timespec="seconds")})


def release_kill_switch(who: str):
    if kill_switch().exists():
        kill_switch().unlink()
    _append({"event": "kill_switch_released", "who": who,
             "at": datetime.datetime.now().isoformat(timespec="seconds")})
