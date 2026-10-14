# ZTO Witness

Check the assigned ZTO/IMD Uniswap v4 pool against two read-only Ethereum RPC
endpoints at the same pinned block before releasing a planning minimum. Python
3.10+ and the standard library only; uses the committed `zto-path` decoder and
quote implementation. It never reads environment variables, wallets or keys,
and it has no signing or transaction methods.

One command from the repository root to make a fresh two-endpoint check:

```sh
python3 -B line-1/tools/zto-witness/zto_witness.py --live --block finalized --word-radius 0 --input ZTO --amount 1 --slippage-bps 100
```

When tried on 2026-10-14, PublicNode and dRPC agreed on the pinned pool state at
block `0x18f9e4b` (`0x8141821630fb19abb73e993875d0102feec3e2d7a16a74f5bf140a65540f8d16`).
Both V4Quoter calls matched the complete local 1-ZTO estimate: **0.000021060151485422
IMD**, with a 100-bps planning minimum of **0.000020849549970567 IMD**. The
report returned `corroborated` and released the raw planning bound. This is the
endpoint response at that pinned historical block, not a continuing freshness
promise or proof that the URLs use independent providers.

The offline demo decodes the saved pool capture at block 26,184,260 and computes
the 1-ZTO local estimate. It leaves `bound_released` false because one archived
capture cannot stand in for two endpoint observations:

```sh
python3 -B line-1/tools/zto-witness/zto_witness.py --demo
```

To make a fresh read, the default endpoints are Ethereum PublicNode and dRPC:

```sh
python3 -B line-1/tools/zto-witness/zto_witness.py --live --block finalized --input ZTO --amount 1 --slippage-bps 100
```

For the same block height, the tool captures PoolManager state and all
initialized ticks in the requested bitmap radius from each endpoint, compares
the exact block hash and state/coverage, then asks each endpoint's deployed
V4Quoter for the same exact-input quote at that block. The tool releases a
raw estimated output and a floor-rounded planning minimum only when both
complete local calculations agree and both Quoter outputs match. Use
`--rpc-a URL --rpc-b URL` to select two HTTPS endpoints explicitly;
`--word-radius 0..4` controls bounded tick coverage. `--block` accepts
`finalized`, `safe`, `latest`, or a decimal block height. `--save-report PATH`
writes the compact result inside the workspace.

Six focused offline tests passed, including block-hash, pool-state, and quoter
disagreement refusals and positive raw-unit minimum rounding:

```sh
python3 -B -m unittest discover -s line-1/tools/zto-witness -p 'test_*.py' -v
```

The two URLs are transport labels, not proof of independent upstreams or
Ethereum consensus. The reported minimum is a planning threshold only; it is
not enforced by a router or receipt. Pool settlement, transfer behavior, gas,
MEV, future liquidity, and execution are outside this tool's scope. ZTO is the
input by default and IMD is the output.
