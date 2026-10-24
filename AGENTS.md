


Whenever we have to implement something, debug something, analyze something, figure something out that is not clear from the beginning, keep a DIARY.md during the conversation where you take notes for yourself, especially what did we try, what did not work, why did it not work, what did work, and so on. Also keep the DIARY.md  in a form that you can later use it yourself to write a proper documentation for whatever we build in the conversation.

## Core Principle

Solve the current task as simply as possible.

Optimize for:

- readability
- directness
- quick understanding (now and months later)

Do NOT optimize for:

- reusability
- scalability
- architectural purity

Small scripts should feel like small scripts — not like the start of a framework.

## Default Approach (Python)

For small tasks:

- Use a **single file**
- Structure:
  - imports
  - small helper functions (only if needed)
  - `if __name__ == "__main__":`
- Prefer **linear, easy-to-follow code**
- Use the **standard library** whenever possible

Avoid:

- unnecessary classes
- splitting into multiple files
- overengineering

## Abstraction Rules

Before introducing abstraction, ask:

> Does this make the code easier to understand right now?

If not:

- do NOT introduce it

Specifically avoid:

- helper functions used only once (unless they clearly improve readability)
- generic utilities for hypothetical reuse
- future-proofing without a concrete need

## Complexity Thresholds

- < 50 lines:

  - keep everything in one file
  - minimal structure
- ~50+ lines:

  - consider small functions for clarity
- ~100+ lines:

  - consider splitting into a second file **only if it improves readability**

Never split code into multiple files by default.

## Error Handling

- Handle realistic, relevant errors only
- Do NOT add defensive code for unlikely edge cases
- Keep error handling simple and readable

## Tooling & Patterns

- Avoid `argparse` unless explicitly needed
- Classes: only if they clearly improve structure
- Type hints: optional, not mandatory
- `dataclasses`: use sparingly
- Config (JSON/YAML): OK if it simplifies usage

Prefer:

- simple functions
- explicit logic
- minimal indirection

## Readability

Code should be understandable by:

- a technical person
- who did not write it
- and reads it again after weeks/months

Prefer:

- explicit over clever
- slightly repetitive over abstract
- clear naming over compactness

## Comments

- Write comments when they help understanding
- Keep them **practical and concise**
- Explain *why*, not obvious *what*

## Final Rule

Do not introduce complexity unless it clearly reduces complexity.
schmijul@schmijul-20FQ0044GE:~$ cat /home/schmijul/.codex/AGENTS.md

# AGENTS.md — Coding Style Guidelines

## Core Principle

Solve the current task as simply as possible.

Optimize for:

- readability
- directness
- quick understanding (now and months later)

Do NOT optimize for:

- reusability
- scalability
- architectural purity

Small scripts should feel like small scripts — not like the start of a framework.

## Default Approach (Python)

For small tasks:

- Use a **single file**
- Structure:
  - imports
  - small helper functions (only if needed)
  - `if __name__ == "__main__":`
- Prefer **linear, easy-to-follow code**
- Use the **standard library** whenever possible

Avoid:

- unnecessary classes
- splitting into multiple files
- overengineering

## Abstraction Rules

Before introducing abstraction, ask:

> Does this make the code easier to understand right now?

If not:

- do NOT introduce it

Specifically avoid:

- helper functions used only once (unless they clearly improve readability)
- generic utilities for hypothetical reuse
- future-proofing without a concrete need

## Complexity Thresholds

- < 50 lines:

  - keep everything in one file
  - minimal structure
- ~50+ lines:

  - consider small functions for clarity
- ~100+ lines:

  - consider splitting into a second file **only if it improves readability**

Never split code into multiple files by default.

## Error Handling

- Handle realistic, relevant errors only
- Do NOT add defensive code for unlikely edge cases
- Keep error handling simple and readable

## Tooling & Patterns

- Avoid `argparse` unless explicitly needed
- Classes: only if they clearly improve structure
- Type hints: optional, not mandatory
- `dataclasses`: use sparingly
- Config (JSON/YAML): OK if it simplifies usage

Prefer:

- simple functions
- explicit logic
- minimal indirection

## Readability

Code should be understandable by:

- a technical person
- who did not write it
- and reads it again after weeks/months

Prefer:

- explicit over clever
- slightly repetitive over abstract
- clear naming over compactness

## Comments

- Write comments when they help understanding
- Keep them **practical and concise**
- Explain *why*, not obvious *what*

## Final Rule

Do not introduce complexity unless it clearly reduces complexity.
