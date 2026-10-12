# Annotation Guide

This is the initial annotation reference for the repair-intake task. The rules below are proposed conventions to validate during the first implementation milestone, not a completed annotation standard.

## Scope

- Use synthetic English conversations about one household appliance.
- Use two known speaker roles and approximately two to five minutes of audio per conversation.
- Create a gold form for selected transcript prefixes, not only for the completed conversation.
- Keep gold annotations separate from model inputs. A provider may see only the transcript prefix and task configuration available at that point.

## Fields

The canonical machine-readable definition is [`configs/tasks/repair-intake.yaml`](../configs/tasks/repair-intake.yaml). It defines the stable field IDs, types, unknown representation, evidence references, and correction policy.

| Field ID | Type | Example value | Annotation intent |
| --- | --- | --- | --- |
| `appliance` | string or null | Washing machine | The single appliance being discussed |
| `location` | string or null | Laundry room | Where the appliance or issue is located |
| `active_leak` | boolean or null | `false` | Whether the leak is active at the latest visible turn |
| `preferred_appointment` | string or null | Saturday afternoon | The latest explicit appointment preference, in the customer's wording |
| `quote_required` | boolean or null | `true` | Whether the customer explicitly requires a quote before work |
| `spending_limit` | money object or null | Unknown | An explicitly stated spending maximum, with amount and currency |

For boolean fields, `true` and `false` are both known answers; `null` means unknown. For `spending_limit`, a known value contains an amount and an ISO 4217 currency code when stated. An unstated currency remains null rather than being inferred.

## Proposed annotation rules

- **Unknown is not absent.** Use unknown when the conversation provides no answer. Use an explicit negative or absent state only when the speaker supports it.
- **Use only available evidence.** Annotate each prefix from information spoken by that point. Do not use future turns to resolve an earlier snapshot.
- **Apply corrections prospectively.** When a speaker revises a value, the new value is current from that turn onward; retain the earlier value in the revision history rather than erasing it.
- **Preserve evidence.** Each populated value should point to the supporting transcript event or source span. Do not invent evidence for an inferred value.
- **Use stable source offsets.** Evidence spans identify an event and a zero-based, half-open character range in that event's text; offsets count Unicode code points.
- **Do not over-interpret.** Keep exact dates and amounts tied to their source wording; leave them unknown when the speaker has not supplied them.
- **Select exact-value candidates.** For appointment preferences and spending limits, select from extracted candidates. Code copies the selected source span and performs any normalization.
- **Separate speaker roles.** Record who said the information when the role is available; do not treat an assistant's question as evidence of the answer.

## Example

Given the conversation:

> “The washing machine is leaking in the laundry room. I turned it off, so it has stopped. Friday morning works … actually, Saturday afternoon. Please give me a quote before doing any work.”

The final snapshot should record `appliance: "Washing machine"`, `location: "Laundry room"`, `active_leak: false`, `preferred_appointment: "Saturday afternoon"`, `quote_required: true`, and `spending_limit: null`. Earlier snapshots should reflect only what was available at their respective transcript prefixes.

## Review checklist

- Is every non-unknown value supported by evidence in this prefix?
- Is a stated absence distinguished from a missing answer?
- Were corrections applied only from the turn where they occurred?
- Were unsupported details, including dates or spending limits, left unknown?
- Does each annotation conform to the field IDs and value types in the canonical task file?