# Sequence

<!-- An order and a critical path, never code. One numbered group per
     requirement. Check a box only with fresh evidence: the command, run, and
     what it printed. -->

- **Order:** <!-- why this order: which requirement unblocks which -->
- **Wiring point:** <!-- where the requirements meet a real entry point -->
- **Story test:** <!-- `tests/acceptance/...::...`, red until the last group
  lands -- or N-A for a single-requirement change -->

## 1. <REQUIREMENT-ID>

- [ ] 1.1 /accept <REQUIREMENT-ID> -- the test is red, for the right reason
- [ ] 1.2 /tdd -- every scenario of <REQUIREMENT-ID>, counter-example included, asserted and green

<!-- An evaluated requirement instead:
- [ ] n.1 /eval <REQUIREMENT-ID> -- the scored check exists, marked live; threshold agreed, or OPEN with an owner -->

## 2. Wiring

- [ ] 2.1 The story test is green through the real entry point
- [ ] 2.2 The full check passes (`[commands].check` in sdd.toml)
