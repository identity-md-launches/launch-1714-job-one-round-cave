# Allowance Spender Code

For each spender with a nonzero allowance in saved Allowance Lens or Allowance Changes evidence, fetches Ethereum runtime bytecode at the exact evidence block hash. It checks chain identity and that the block hash still resolves, then reports whether runtime code was present, its byte length and a SHA-256 digest. It uses Ethereum mainnet and the existing real ZTO-first/IMD-second evidence; no fabricated owner, token or spender is introduced.

From the repository root, one command shows it working against the bundled real ZTO inventory:

```sh
python3 -B line-2/tools/spender-code/spender_code.py
```

On 2026-10-14, the command was tried against Ethereum PublicNode using block 26,187,572, hash `0xfbdf6fb511bd7ee2e74dd1b2bd8982e05e2d4cf8d10e495e6b9789bc50e7997f`. It found 19 measured pairs, three active owner-spender pairs, and two distinct active spenders. Both returned nonempty runtime code at that same historical block: 2,133 and 8,285 bytes. No `eth_send*`, transaction, wallet or signing method is used.

Optional inputs:

```sh
python3 -B line-2/tools/spender-code/spender_code.py --observation line-2/tools/bundle-refresh/live-after.json --endpoint https://eth.drpc.org --timeout 25
```

The endpoint must be one of the two public Ethereum routes in the code. The `User-Agent` is `IdentityMD-Pepeolithic-Line2-SpenderCode/1.0`. The overall RPC deadline covers chain, block and code calls. Inputs are restricted to the workspace and validated through Allowance Changes. RPC claims are trusted and not proofs; empty code does not prove an EOA or safety, and code presence does not identify a controller, proxy target, source or behavior. It covers only measured active standard ERC-20 allowances and is not a full wallet audit. It reads no environment variables or secrets, writes no report by default, and does not sign, send, simulate, pay or post.
