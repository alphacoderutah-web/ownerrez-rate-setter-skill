# OwnerRez Rate Setter Skill

A Claude Code skill for changing nightly rates on **OwnerRez** properties priced by
**PriceLabs** — without the change you didn't mean to make.

A booking taken at the wrong rate cannot be recalled. That asymmetry shapes the whole
design: every change passes through a guard that fails closed, and the guard's refusals
matter more than its approvals.

Works with any OwnerRez portfolio. It ships its own tooling and **starts read-only**, so
installing it can never reprice anything.

## What you get

- **A write guard** — mode, size caps, weekly frequency caps, a cooldown, a kill switch,
  and a full audit log. Fails closed on missing or corrupt config.
- **Dry run by default** — `--execute` is always explicit.
- **Per-change human approval** bound to one exact change, with a 15-minute expiry.
- **Verified read-back** — a `200` from PriceLabs is not proof the value stuck.
- **One-command rollback**, reconstructed from the audit log.
- **Identity you can trust** — properties resolve through a built map, and ambiguous names
  are refused rather than guessed.
- **`references/pricing-judgment.md`** — ten expensive mistakes, each from a real portfolio.

## Install

```bash
git clone https://github.com/alphacoderutah-web/ownerrez-rate-setter-skill
cp -r ownerrez-rate-setter-skill/ownerrez-rate-setter ~/.claude/skills/
```

Or drop `ownerrez-rate-setter/` into a project's `.claude/skills/`.

Needs Python 3.9+ and `requests`.

## Setup

Credentials live in environment variables, never in config or this repo:

```bash
export OWNERREZ_USERNAME="..."     # OwnerRez: Settings -> API Access
export OWNERREZ_TOKEN="pt_..."
export PRICELABS_KEY="..."         # PriceLabs: Account -> API
```

```bash
python scripts/setup.py --init     # creates .rate-setter/config.json, mode SHADOW
python scripts/setup.py --check    # confirms both APIs answer
python scripts/setup.py --map      # pairs OwnerRez properties to PriceLabs listings
```

Several accounts? Suffix each variable with the account name (`OWNERREZ_TOKEN_FLORIDA`)
and run `--init --accounts florida utah`.

## Use

```bash
# dry run - reads live state, shows the guard's verdict, writes nothing
python scripts/set_rates.py --unit "Beach House" --base 440

# apply
python scripts/set_rates.py --unit "Beach House" --base 440 --execute \
    --reason "pacing 12pp ahead of market at 30 and 60 days" --approved-by Sam

# undo
python scripts/rollback.py --unit "Beach House" --execute --approved-by Sam
```

## Modes

Writes are off until you turn them on by editing `.rate-setter/config.json`.

| Mode | Behaviour |
|---|---|
| `SHADOW` | Read-only. Proposes, never writes. **The default.** |
| `APPROVE_EXECUTE` | Proposes; a named human approves each change; then writes. |
| `BOUNDED_AUTONOMY` | Writes within the caps, no per-change approval. |
| `FULL_AUTONOMY` | Writes without caps. Rarely the right answer. |

`unit_modes` overrides the global mode per property, so you can pilot one unit before
trusting the portfolio.

## Prove it before you trust it

```bash
python scripts/test_guard.py     # 26 cases, mostly negative
```

Mostly *negative* cases on purpose: a guard is only worth having if its refusals are
reliable. It covers SHADOW, the kill switch, oversized and too-frequent changes, cooldown,
malformed values, missing and corrupt config, approval matching and expiry, cap overrides,
and per-unit mode isolation. No network calls, no effect on your data.

## Defaults, and why

| Setting | Default | Reasoning |
|---|---|---|
| Mode | `SHADOW` | Installing a tool should never change your prices. |
| Max change | 7% | Large moves are usually chasing noise; they stay possible, but need a person. |
| Changes per unit per week | 2 | More than that is generally reacting, not managing. |
| Cooldown | 3 days | A change needs time to show an effect before another lands on top. |
| Maximum price | **prohibited** | Capping your own upside is the most common expensive mistake in dynamic pricing. Cap individual dates instead. |

All adjustable in `.rate-setter/config.json` — except the maximum-price prohibition, which
is enforced in the guard.

## What it doesn't do

- **Airbnb or Vrbo promotions** — no API exists; those are set by hand. It does warn that
  channel discounts stack on top of PriceLabs and can push a realised rate below your floor.
- **Availability, minimum-night stays, or listing content.**
- **Decide whether a unit should be writable** — that's yours, and the skill will not
  advance its own mode.

## Licence

MIT. No warranty — it changes prices on your live listings when you tell it to. Run the
tests, start in `SHADOW`, and pilot one unit first.
