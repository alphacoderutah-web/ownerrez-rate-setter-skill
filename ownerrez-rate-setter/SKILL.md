---
name: ownerrez-rate-setter
description: Safely change nightly base and minimum prices for OwnerRez properties priced by PriceLabs, with a write guard, dry runs, per-change human approval, verified read-back and one-command rollback. Use whenever someone wants to adjust a rate — "raise the beach house to 440", "drop the minimum on unit 3", "apply the pricing recommendation", "undo yesterday's price change", "why was that rejected?" — and also when a rate change is merely implied by a pricing decision that has just been agreed. Works for any OwnerRez + PriceLabs portfolio; installs its own tooling and starts read-only.
---

# OwnerRez rate setter

A booking taken at the wrong rate cannot be recalled. That asymmetry — cheap to be slow, expensive to be wrong — shapes everything here: every change passes through a guard that fails closed, and the guard's refusals matter more than its approvals.

Works with any OwnerRez portfolio priced by PriceLabs. It ships its own tooling and starts in read-only mode, so installing it can never reprice anything.

## The one rule

**You may propose. Only a named human may authorise.** Everything below elaborates on that. When the guard says no, report why and stop — don't hunt for a flag that makes it say yes.

## Non-negotiables

1. **Dry run first, every time.** `set_rates.py` writes nothing without `--execute`. Run it bare, read the verdict, show the human, and only then consider executing. The dry run costs seconds and is the entire safety margin.
2. **Never add `--execute` on your own initiative.** It belongs on the command line only when a human has asked for *that specific change*. "Take a look at pricing" is not authorisation to write.
3. **Never invent `--approved-by`.** That field records who is accountable. A name the person didn't give you is a falsified audit record.
4. **Never reach for `--override-caps` to get around a denial.** An override is a separate, explicit decision a human makes knowing they're exceeding a limit — not a retry strategy.
5. **A denial is not an error.** Don't retry it, don't work around it. Report the reason plainly and let the human decide.
6. **Resolve identity through the property map, never by eyeballing a name.** Names repeat, and one physical home is often listed twice. `properties.py` refuses ambiguous matches rather than guessing.

## First-time setup

Credentials live in environment variables, never in config or the repo.

```bash
# single account
export OWNERREZ_USERNAME="..."      # OwnerRez API username
export OWNERREZ_TOKEN="pt_..."      # OwnerRez API access token
export PRICELABS_KEY="..."          # PriceLabs API key
```

Get the OwnerRez token at **Settings → API Access**, and the PriceLabs key at **Account → API**. For several accounts, suffix each variable with the account name in caps (`OWNERREZ_TOKEN_FLORIDA`, `PRICELABS_KEY_UTAH`) and list them at init.

```bash
python scripts/setup.py --init                       # or: --init --accounts florida utah
python scripts/setup.py --check                      # verifies both APIs answer
python scripts/setup.py --map                        # pairs OwnerRez properties to PriceLabs
python scripts/setup.py --status                     # mode, caps, map, audit summary
```

This creates `.rate-setter/` beside your project holding config, the property map, the audit log, and the kill switch. **Mode starts at `SHADOW`** — read-only. Turning writes on is a deliberate human edit to `.rate-setter/config.json`:

| Mode | Behaviour |
|---|---|
| `SHADOW` | Read-only. Proposes, never writes. The default. |
| `APPROVE_EXECUTE` | Agent proposes, a named human approves each change, then it writes. |
| `BOUNDED_AUTONOMY` | Writes within the caps without per-change approval. |
| `FULL_AUTONOMY` | Writes without caps. Rarely the right answer. |

`unit_modes` overrides the global mode for named properties, which is how you pilot one unit before trusting the whole portfolio.

## Order of operations

```
pin the unit → read live state → sanity-check the number → dry run
   → show the verdict → (human authorises) → execute → verify read-back → Sync Now
```

## Step 1 — Pin the unit and read what is live

```bash
python scripts/set_rates.py --unit "Beach House" --base 440
```

With no `--execute` this prints the unit, account, PriceLabs listing id, the **live** base/min/max, the effective mode, and a guard verdict per change. Read the live values before trusting any number you were handed — a base quoted from a report may be days stale.

If the property isn't found, rebuild the map (`--map`) rather than forcing a match.

## Step 2 — Sanity-check the number before proposing it

The mechanics are safe; judgment is where money is lost. `references/pricing-judgment.md` covers this properly — read it when you're deciding *what* number to set rather than how to set it. The short version:

- **Base is a global lever.** It moves every date, including next year's peak. Fix one soft month with a date-limited override, not a base cut.
- **Check fees before cutting rent.** If the guest-facing price is high because of *fees*, cutting rent can't fix it and permanently lowers your anchor.
- **Don't raise on a unit with nothing left to sell.** A base raise on a full calendar is noise.
- **Channel discounts stack on top.** Airbnb and Vrbo promotions apply to whatever PriceLabs pushes, and can drive the realised rate below your own minimum without anything showing in PriceLabs.

## Step 3 — Read the guard's verdict properly

Each denial means something specific and calls for a different response.

| Verdict | What it means | What to do |
|---|---|---|
| `mode is SHADOW` | This unit has no write authority. | Report it. Enabling writes is the owner's decision, not something to route around. |
| `KILL SWITCH ACTIVE` | Something halted writes. | Find out **why** before releasing it. Read `.rate-setter/KILL-SWITCH` and the recent audit entries. |
| `change X exceeds cap` | Size cap. | Propose a smaller change, or put the override question to the human explicitly. |
| `N change(s) already applied … last 7 days` | Frequency cap. | Wait, or escalate deliberately. Repeated same-week edits usually mean chasing noise. |
| `cooldown: … within the N-day cooldown` | A change needs time to show an effect. | Wait. Re-cutting after a day is how oscillation starts. |
| `APPROVE_EXECUTE mode - human approval required` | Working as designed. | Get a real name, then pass `--approved-by`. |
| `GUARD FAILED CLOSED: …` | Config missing or unreadable. | Fix the config. Never bypass — failing closed *is* the guard working. |
| `setting a maximum price is prohibited` | A max price caps your own upside. | Use a date-specific override instead. |

## Step 4 — Execute, once a human has actually asked

```bash
python scripts/set_rates.py --unit "Beach House" --base 440 --execute \
    --reason "pacing 12pp ahead of market at 30 and 60 days" --approved-by Sam
```

`--reason` lands in the permanent audit record. Write it for someone reading the log in six months with no memory of this conversation: what moved, and on what evidence.

In `APPROVE_EXECUTE` the tool prompts and requires the unit name typed back. That prompt is a human checkpoint. `--yes` skips it for non-interactive runs, but only when the human has already approved this exact change — using it to skip a confirmation nobody gave defeats the point.

## Step 5 — Verify, then sync

A `200` is not proof the value stuck. Every applied change is read back automatically; if the read-back disagrees, **stop and investigate before making further changes** rather than retrying.

Then tell the human to press **Sync Now** in PriceLabs. Without it, changes can take about a day to reach the channels — long enough for someone to conclude the change didn't work and cut again.

## Rolling back

```bash
python scripts/rollback.py --unit "Beach House"                    # plan only
python scripts/rollback.py --since 2026-08-17T00:00 --execute --approved-by Sam
```

Rollback plans by default and still passes through the guard, so it can't be used as a side door. It restores the value held *before* the earliest change in scope, not a chain of intermediate steps. `--emergency` clears the cooldown and frequency caps only — never the kill switch, never the mode.

## When something looks wrong mid-flight

Stopping is cheap:

```bash
python -c "import sys; sys.path.insert(0,'scripts'); import guard; guard.engage_kill_switch('claude','<why>')"
```

Every write halts until a human deletes `.rate-setter/KILL-SWITCH`. Understand the cause before releasing it.

## Proving the guard works

Before trusting this with real money, run the test suite. It's mostly *negative* cases — a guard is only worth having if its refusals are reliable.

```bash
python scripts/test_guard.py
```

## What this skill does not do

- **Airbnb or Vrbo promotions.** No API path exists; those are set by hand.
- **Availability, minimum-night stays, or listing content.**
- **Deciding whether a unit should be writable.** That's the owner's call, recorded in `.rate-setter/config.json`. Never advance the mode yourself.

## Files

| Path | What it holds |
|---|---|
| `scripts/guard.py` | The choke point. Mode, caps, cooldown, kill switch, approvals, audit. |
| `scripts/pricelabs.py` | The only module that may issue a mutating PriceLabs call. |
| `scripts/properties.py` | Identity. Pairs OwnerRez properties to PriceLabs listings. |
| `scripts/set_rates.py` / `rollback.py` | The two CLIs. |
| `scripts/setup.py` | Init, credential check, map build, status. |
| `scripts/test_guard.py` | Failure-mode tests. |
| `references/pricing-judgment.md` | What to set, and the mistakes that cost real money. |
| `.rate-setter/` | Your config, property map, audit log, kill switch. |
