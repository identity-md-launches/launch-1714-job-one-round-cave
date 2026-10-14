# Return Relations checks

The documented offline command succeeds:

```sh
python3 -B line-4/tools/return-relations/return_relations.py demo
```

It returns `consistent` for the saved real ZTO PoolManager balance versus total
supply, in the same block and declared raw ZTO units. The full ZTO-first/IMD-second
set is required even though the relation selects only its two ZTO members.
The inherited historical expiry policy is explicit demonstration input, not a
current-time claim. The saved transport is a contributor relay with unverified
upstream independence; no new chain request was made.

79 tests pass: 19 Return Relations, 21 Set Expiry, 27 Rehearsal Set, and 12
Return Lens. `check-results-36.json` records commands, exit codes and full output.
Cases include all six comparisons, equality boundaries, signed tuple values,
every-relation enforcement, exact full-policy digest binding, changed unselected
evidence, missing calls, missing sender, reverts, expired policies, pre-block
review times, unknown members, canonical integer ABI consumption, unit mismatch,
duplicate/unused declarations, malformed references, immutable inputs and CLI
exit categories. The demo test forbids RPC calls.

The new tool imports existing standard-library validators and decoders without
modifying them. No packages were installed. No deployment, key, wallet, secret,
environment lookup, signature, payment, post or transaction submission was used.

Visual and structural checks: restored ancestor SHA-256 matched record 35;
finished PNGs are identical, square and 1254px; JPEG is 512px and below 100 KB;
6,000 changed pixels are entirely inside the declared bare-stone patch.
`VISUAL-36.md` records inspection and the preserved ancestral digit ambiguity.
Record 36 contains exactly the requested six attributes and final image hash.
GOAL.md and every older record are unchanged; only assigned paths were modified.
