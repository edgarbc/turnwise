# Annotation Guide

This is the initial annotation reference for the repair-intake task. The rules below are proposed conventions to validate during the first implementation milestone, not a completed annotation standard.

## Scope

- Use synthetic English conversations about one household appliance.
- Use two known speaker roles and approximately two to five minutes of audio per conversation.
- Create a gold form for selected transcript prefixes, not only for the completed conversation.
- Keep gold annotations separate from model inputs. A provider may see only the transcript prefix and task configuration available at that point.

## Fields

| Field | Example value | Annotation intent |
| --- | --- | --- |
| Appliance | Washing machine | The appliance being discussed |
| Location | Laundry room | Where the appliance or issue is located |
| Active leak | Explicitly absent now | Whether the leak is currently active, including clear negation |
| Preferred appointment | Saturday afternoon | The latest stated appointment preference |
| Quote required | Yes | Whether a quote is requested before work |
| Spending limit | Unknown | A limit stated by the speaker; do not infer one |

## Proposed annotation rules

- **Unknown is not absent.** Use unknown when the conversation provides no answer. Use an explicit negative or absent state only when the speaker supports it.
- **Use only available evidence.** Annotate each prefix from information spoken by that point. Do not use future turns to resolve an earlier snapshot.
- **Apply corrections prospectively.** When a speaker revises a value, the new value is current from that turn onward; retain the earlier value in the revision history rather than erasing it.
- **Preserve evidence.** Each populated value should point to the supporting transcript event or source span. Do not invent evidence for an inferred value.
- **Do not over-interpret.** Keep exact dates and amounts tied to their source wording; leave them unknown when the speaker has not supplied them.
- **Separate speaker roles.** Record who said the information when the role is available; do not treat an assistant's question as evidence of the answer.

## Example

Given the conversation:

> “The washing machine is leaking in the laundry room. I turned it off, so it has stopped. Friday morning works … actually, Saturday afternoon. Please give me a quote before doing any work.”

The final snapshot should record the washing machine, laundry room, leak explicitly absent now, Saturday afternoon, quote required, and spending limit unknown. Earlier snapshots should reflect only what was available at their respective transcript prefixes.

## Review checklist

- Is every non-unknown value supported by evidence in this prefix?
- Is a stated absence distinguished from a missing answer?
- Were corrections applied only from the turn where they occurred?
- Were unsupported details, including dates or spending limits, left unknown?
- Does each annotation conform to the canonical task labels once those are defined?