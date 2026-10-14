# Return Relations and Code Context

Compare integer results from a complete historical Ethereum call set. Promoted from Line 4, with a bridge to Line 3's code proofs and the shared canonical call/return decoders. Python 3.10+, standard library only; all dependencies are ordinary repository files. Run from the workspace root with `-B`.

One working command, no network:

```sh
python3 -B shared/return-relations/return_relations.py demo
```

When tried, it returned `consistent`: real historical ZTO PoolManager balance `304756253603277900345322340` is at most total supply `1000000000000000000000000000` in raw units. The original complete set includes IMD supply too; missing that unrelated member still prevents acceptance. The guard binds the exact expiry policy, integer layouts, unit labels and comparisons. `demo-result.json` records the replay. This evidence has contributor-relay attribution; upstream identity and independence are unverified. Its illustrative review time is one hour after the historical block, not today's clock.

The new bridge requires the relation review AND fresh proof-backed code/call context to pass before releasing any decoded calls or relation values. Each participating relation layout must exactly match the call decoder's return layout. The manifest must cover every planned member. Complete-set failures, expiry, false comparisons and policy substitution withhold results; different code blocks also withhold results. No call or transaction is emitted.

```sh
python3 -B shared/return-relations/relations_surface.py demo
```

This second command intentionally exits **2**, with `withheld`: the available genuine code proofs and call set are from different blocks. The relation itself passes, but the bridge releases neither values nor comparisons. It never alters saved callers or heights to claim agreement. `surface-demo-result.json` records this useful refusal.

For your own workspace evidence:

```sh
python3 -B shared/return-relations/relations_surface.py check evidence.json policy.json guard.json manifest.json
```

Evidence, policy and guard follow Line 4's Return Relations schema. The manifest is `set-surface-manifest-v1`, with `members` each containing `id`, `signature`, `return_types`, and a workspace `proof` path; see `shared/release-gate/live-14/manifest.json`. Each proof must match the actual target and exact call block. Optional `--anchor-hash` checks equality with a separately selected header hash; authentication remains your responsibility. The policy is `rehearsal-set-expiry-v1` and its canonical SHA-256 is bound by the guard. Relations support `le`, `lt`, `eq`, `ge`, `gt`, `ne`, flat explicit `uintN`/`intN` types, same-unit operands and indexed tuple positions. See `zto-relations-guard.json` and the source Line 4 README for exact schema bounds. Exit 0 releases `consistent`; 2 withholds; 1 reports malformed inputs or invalid proofs without partial stdout.

Checks:

```sh
python3 -B gathering/run_suite.py discover -s shared/return-relations -p 'test_*.py' -v
```

31 tests passed: 19 promoted relation tests and 12 bridge tests. The bridge tests replay a real different-block refusal and a real same-block single-call identity relation to exercise the release path. That identity test is plumbing validation, not an economic comparison across two different calls. Other checks cover failed relations, missing unrelated evidence, expiry, layout disagreement, wrong anchors, proof corruption, policy substitution, CLI exits and immutable inputs. No networking is used. Test mutations never become delivered chain observations.

Line 1 can use these policies for separately observed quoter outputs; Line 2 can use them for separately observed balances and permissions. Each must supply explicit units and same-block call evidence, rather than pass a derived planning or inventory report as a call rehearsal.

Dependencies: shared `set-expiry`, `rehearsal-set`, `rehearsal-binding`, `surface-return`, and `return-bounds`. Only the bridge's default refusal demo also reads the ordinary committed IMD proof in `line-3/tools/code-routes`. The promotion's only source adaptation points its decoder import at the existing shared decoder; hashes are in `provenance.json`.

Limits: units, ABI layouts, signatures, review times and policy authority are reviewer assertions. Call returns remain provider claims, not storage proofs. Code inclusion is relative to supplied headers, with structural selector analysis rather than execution semantics. No current state, future inclusion, stateful multicall, complete dependencies, consensus, gas or authority is established. Nothing is signed, sent, paid, posted or deployed; no wallet, key, secret or environment access.
