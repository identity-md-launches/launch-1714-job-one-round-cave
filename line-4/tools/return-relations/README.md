# Return Relations

Compare integer results of separate Ethereum call rehearsals at one exact historical
block. A reviewer can require, for example, a token balance to be no greater than
its total supply. Unlike independent bounds, the limit is another rehearsed return.
Every member of the declared set must match, including calls not used by a relation.

From the repository root, with Python 3.10 or later:

```sh
python3 -B line-4/tools/return-relations/return_relations.py demo
```

This offline command returned `consistent` with the inherited real ZTO evidence:
PoolManager balance `304756253603277900345322340` is at most total supply
`1000000000000000000000000000`, in raw ZTO units. The exact historical block,
provider attribution, guard and policy digests appear in `demo-result.json`.
The evidence uses the ancestor's contributor relay: upstream identity and
independence are unverified. The demonstrated review time is one hour after the
saved block, not an assertion that this evidence is fresh today. No new chain call
is necessary for this demo; no network is used by this tool.

## Own review

```sh
python3 -B line-4/tools/return-relations/return_relations.py check evidence.json policy.json guard.json
python3 -B -m unittest discover -s line-4/tools/return-relations -p 'test_*.py' -v
```

Use the sibling Rehearsal Set evidence schema and Set Expiry policy schema.
The latter contains the complete explicit call plan, block and review-time window.
`guard.json` has exactly `schema`, `policy_sha256`, `layouts` and `relations`;
see `zto-relations-guard.json`. The digest is SHA-256 of the normalized full
Set Expiry policy using Rehearsal Binding's canonical JSON `digest` function.
A changed caller, block, expected return or age policy requires a new reviewed
digest; it still must pass complete evidence binding.

Each layout has a unique `id` naming a planned call, a flat `types` array of explicit
`uintN` or `intN` types (N is 8 through 256 in steps of 8), and a `unit` label.
All positions in a layout share that label. Each relation has a unique `id`,
`left` and `right` references (`id` and zero-based integer `index`), and `op`:
`le`, `lt`, `eq`, `ge`, `gt` or `ne`. Both operands require the same unit label.
Every layout must participate; unrelated plan members still need evidence.
Layouts and relations each have 1–32 entries. Inputs are bounded to 95 KB,
reject unknown fields and duplicate JSON keys, and must be inside the workspace.
Canonical ABI padding, integer width and exact byte consumption are required.

Exit 0 means `consistent`; 1 means `withheld` (false relation, changed policy,
mismatched evidence or expiry); 2 means `inconclusive` (missing evidence, bad
layout, malformed input or a review time preceding the block). All relations
must pass. No unsigned call is emitted. Failed complete-set checks prevent
decoding; failed layouts expose no partial decoded values.

## Limits and dependencies

Unit labels are reviewer assertions, not verified decimals or token identity.
Using the same label for unlike assets can produce a meaningless comparison.
Types and relations are not authenticated ABI or economic claims. Provider
claims can be false, and digests identify content rather than a trusted reviewer.
Historical independent calls do not simulate a write sequence, multicall or future
transaction. This tool does not establish present state, gas, authority, effects
or future success. It reads no keys, wallet, secrets or environment and signs,
sends, pays and posts nothing.

Python standard library only. Keep the sibling `set-expiry`, `rehearsal-set`,
`rehearsal-binding`, `call-rehearsal`, `return-lens` and `call-changes` folders:
their existing validation and decoding code is imported without modification.
The saved real set and expiry policy are reused in place, not replaced.
Focused checks cover actual evidence replay, all six operators, inclusive
boundaries, signed tuple indices, failed relations, policy changes, complete-set
failures, expiry, strict units/layouts/references, duplicate keys and CLI exits.
