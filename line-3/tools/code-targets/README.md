# Code Targets

Inventory every decoded external call in a proved historical Ethereum runtime, then group locally constant target operands by their low 160-bit address. All unresolved sites remain explicit. This helps a worker decide which candidate addresses need separate code evidence, without mistaking the existing first-64 preview for a full call inventory.

Run from the repository root with Python 3.9+ and only the standard library:

```sh
python3 -B line-3/tools/code-targets/demo.py
```

When tried, `demonstration_passed` was `true`. The demonstration reverified the committed real ZTO proof first, then IMD, at Ethereum block **26,188,209**. ZTO has no decoded external calls. IMD has twelve: one locally constant target at byte offset **12,834**, address **0x1a44076050125825900e736c501f859c50fe728c**, and eleven unresolved sites. The metadata-overlapping call remains included and labelled. `demo-result.json` records the full replay. These are saved historical proofs, with no new network capture or independent anchor claimed.

For your own raw Code Proof bundle already inside this workspace:

```text
python3 -B line-3/tools/code-targets/code_targets.py --bundle YOUR_PROOF.json
```

Optionally supply `--anchor-hash` with a separately obtained execution-block hash. Matching that hash binds the evidence to it; authenticating the anchor remains the caller's responsibility. Missing anchors are labelled `unanchored-rpc-header`.

The CLI rechecks every raw account, storage, header and runtime proof before releasing any findings. It prints JSON and writes no files. Valid inspection exits 0, including unresolved targets. Invalid evidence or a wrong anchor exits 1 with empty stdout; invalid argument syntax exits 2. Workspace-escaping paths, oversized evidence and duplicate JSON keys are refused by the inherited loader.

Each runtime lists address-sorted constant target groups, all sites within each group in byte-offset order, and all unresolved sites in byte-offset order. A group's `opcodes` distinguishes CALL, CALLCODE, DELEGATECALL and STATICCALL. Sites retain full 256-bit operand words, so different high bits are not erased when equal low-160-bit addresses are grouped. Zero, if actually derived from code, remains a measured operand, never a supplied missing recipient. Roles identify candidate-path and beacon runtimes without claiming that observed routing is semantically proved.

The inventory bypasses the 64-site preview by requesting batches of at most 32 offsets from the existing full-runtime scanner. It never slices code, so PC and CODESIZE stay correct. The 24,576-byte runtime bound is inherited. Worst-case scanning cost grows with the number of batches; stdout can exceed 100 KB for adversarial runtimes. No oversized result is saved in this delivery.

Tests:

```sh
python3 -B -m unittest discover -s line-3/tools/code-targets -p 'test_*.py' -v
```

All **14 tests passed**, including real evidence with networking disabled, a 101-call inventory beyond the preview, original PC/CODESIZE, PUSH-data exclusion, unresolved calls after STOP, high-word preservation, sorted groups, unchanged input, proof refusal before analysis, anchor matching, runtime bounds and CLI behavior. An independent generated-call oracle checked 60 programs with randomized full-word targets. The first test run exposed a test-only `demo` module-name collision caused by inherited import paths; loading this piece's demo explicitly corrected it, and the complete suite passed afterward.

Dependencies are ordinary committed sibling files: `code-calls`, `code-surface`, `code-opcodes`, `code-ancestry`, `code-proof`, and `code-lens` including Keccak. The demo additionally needs `code-routes/zto-proof.json` and `code-routes/imd-proof.json`. Keep those folders together. No installation, configuration edits, submodules or external packages are needed.

Limits: this is legacy EVM structural byte analysis. All decoded calls are included, including potentially unreachable code and recognized metadata. Constants are conditional on successful linear-segment execution; unknown inputs, memory, storage and control transfers prevent full target recovery. Group membership does not prove actual execution, an external account's identity, current code, complete dependencies, source/ABI equivalence, consensus, finality, anchor authenticity, safety or authority to transact. No environment variables, wallets, keys or secrets are read; nothing is signed, sent, paid, posted or deployed.

The wall mark's description is: **Pepe gathers many call trails around one shared stone.** See `line-3/VISUAL-36.md` for dimensions, format and visual review.
