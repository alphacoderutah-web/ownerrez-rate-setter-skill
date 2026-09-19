---
slug: background
title: Project background
role: project background
updated: "2026-09-18T18:09:56"
---

# Project background

## Why

Changing a nightly rate is cheap to do slowly and expensive to get wrong: a booking taken at the wrong rate cannot be recalled. This skill exists so that Claude can change base and minimum prices for OwnerRez properties priced by PriceLabs **without making a change nobody meant to make**. That asymmetry is the stated design driver; the guard's refusals are treated as more important than its approvals.

The commit history records how it came about: it **generalises an earlier, portfolio-specific rate-setting skill** whose procedure drove scripts living in one private project, which made it inert for anyone else. This version ships its own machinery so any OwnerRez + PriceLabs operator can install and run it (see [[fail-closed-write-guard]]).

## Goals

- Every write passes one guard that **fails closed** ([[fail-closed-write-guard]]).
- **Installing it can never reprice anything**: it starts read-only ([[shadow-by-default-and-write-modes]]).
- Writes happen only with a **named human's approval of one exact change** where the mode requires it ([[approval-bound-to-one-change]]).
- Every applied change is **read back and verified** ([[single-mutating-call-and-read-back]]).
- The right property is always the one changed ([[identity-through-property-map]]).
- Any change can be **undone in one command** from the audit log ([[rollback-from-audit-log]]).

## Non-goals

- Airbnb or Vrbo promotions (no API path; set by hand). The skill does warn that channel discounts stack on top of what PriceLabs pushes.
- Availability, minimum-night stays, or listing content.
- Deciding whether a unit should be writable: that is the owner's edit to local config, and the skill never advances its own mode.
- Deciding *what* number to set on its own authority. The skill may propose; only a named human may authorise. Judgment guidance lives in a separate reference file, apart from the mechanics.

## Target user

Short-term-rental operators whose properties are in OwnerRez and priced by PriceLabs, with one or several accounts, who want Claude to carry out rate changes under hard safeguards and a full audit trail.

**Open question:** the repo records no success measures for the tool itself (for example, how often denials or read-back mismatches are expected).
