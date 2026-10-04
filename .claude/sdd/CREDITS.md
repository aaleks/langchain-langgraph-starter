# Credits

This method is one layer on top of the work of others. What it takes from each,
and the licences that make that possible.

## OpenSpec -- the engine

<https://github.com/Fission-AI/OpenSpec>, MIT. Used as a dependency (pinned,
through `sdd.sh openspec`): the change lifecycle -- proposals as deltas
(ADDED / MODIFIED / REMOVED / RENAMED) that `archive` merges into living specs
-- the schema-defined artifact graph with `status`, `instructions` and
`validate --strict`, and the diagnostic envelope (`severity`, `code`, `message`,
`target`, `fix`) that the proof checker's output follows. The `sdd-proof` schema
follows the structure of OpenSpec's `spec-driven` schema.

> Copyright (c) 2024 OpenSpec Contributors

## Superpowers -- the behaviour

<https://github.com/obra/superpowers>, MIT. Not a dependency: its ideas and some
of its wording are adapted into the skills, so the method works where plugins do
not load (cloud sessions) and speaks one vocabulary. Taken, and adapted:

- the **evidence gate** -- identify the command, run it fresh, read the output,
  only then claim -- and its reach over paraphrases and expressions of
  satisfaction (`/land`, the first law);
- **approval semantics**: a reply approves the stage actually presented;
- **classifying before acting**, said out loud, with a **one-way ratchet**
  (`/intake`; Superpowers has spike, bounded and architectural paths);
- **systematic debugging's four phases** and "three failed fixes means question
  the architecture" (`/debug`);
- the **Iron Laws** quoted in `/tdd` and `/debug`, and rationalisation tables
  built from observed agent behaviour;
- the **finishing-a-branch option menu** (`/land`);
- from *writing-skills*: a description says **when**, never how; **match the form
  to the failure** (prohibition for discipline, recipe for shape, a template slot
  for omission, an observable predicate for a condition); and pressure-testing
  discipline skills (`pressure-tests.md`).

> Copyright (c) 2025 Jesse Vincent
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Spec Kit -- the analyst

<https://github.com/github/spec-kit>, MIT. A donor of ideas, never installed --
two places holding a specification is the failure this method exists to
prevent. Taken: the ambiguity taxonomy marked Clear / Partial / Missing behind
the **coverage screen**; **measurable outcomes kept apart from behaviour**
(the frame's Outcome slot); `/analyze`'s **finding cap** and **automatic
escalation against a named authority** (`/verify`'s non-negotiables); and the
**go / clarify / kill** verdict that ends a spike.

> Copyright GitHub, Inc.

## Where the rest came from

The determinism boundary, requirement-to-test traceability failing the build,
guards on secrets and ground truth, challenge-the-build, measure-before-assert,
and the auditors were built in the project this method came from, each because
something broke. See README, "Where this came from".
