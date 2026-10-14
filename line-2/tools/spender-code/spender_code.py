#!/usr/bin/env python3
"""Read runtime code for spenders with active allowances at the evidence block."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'allowance-changes'))
import allowance_changes as changes

DEFAULT_OBSERVATION = HERE.parent / 'bundle-refresh' / 'live-after.json'
ENDPOINTS = ('https://ethereum-rpc.publicnode.com', 'https://eth.drpc.org')
USER_AGENT = 'IdentityMD-Pepeolithic-Line2-SpenderCode/1.0'


def active_spenders(observation):
    measured = changes.flatten(observation)
    changes.lens.require(measured['chain_id'] == 1, 'only Ethereum chain 1 is supported')
    changes.lens.require(measured['token_address'] in changes.lens.TOKENS.values(),
                         'evidence must be real ZTO or IMD')
    spenders = sorted({spender for (_, spender), row in measured['pairs'].items()
                       if int(row['allowance_raw']) > 0})
    changes.lens.require(bool(spenders), 'evidence has no active spender with a nonzero allowance')
    return measured, spenders


def rpc(url, method, params, request_id, deadline):
    remaining = deadline - time.monotonic()
    changes.lens.require(remaining > 0, 'overall RPC deadline exceeded')
    payload = json.dumps({'jsonrpc': '2.0', 'id': request_id,
                          'method': method, 'params': params}).encode()
    request = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json', 'Accept': 'application/json',
        'User-Agent': USER_AGENT,
    })
    try:
        with urllib.request.urlopen(request, timeout=min(8.0, remaining)) as response:
            raw = response.read(1_000_001)
    except (OSError, urllib.error.URLError) as exc:
        raise ValueError(f'{method} request failed: {exc}') from exc
    changes.lens.require(len(raw) <= 1_000_000, 'RPC response exceeds 1 MB')
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'{method} returned invalid JSON') from exc
    changes.lens.require(isinstance(result, dict) and result.get('jsonrpc') == '2.0'
                         and result.get('id') == request_id,
                         f'{method} returned a mismatched JSON-RPC envelope')
    changes.lens.require('error' not in result, f'{method} RPC error: {result.get("error")}')
    changes.lens.require('result' in result, f'{method} omitted result')
    return result['result']


def inspect(measured, spenders, endpoint=ENDPOINTS[0], timeout=25):
    changes.lens.require(endpoint in ENDPOINTS, 'endpoint must be one of the documented public Ethereum routes')
    changes.lens.require(type(timeout) in (int, float) and 1 <= timeout <= 60,
                         'timeout must be between 1 and 60 seconds')
    deadline = time.monotonic() + timeout
    chain = rpc(endpoint, 'eth_chainId', [], 1, deadline)
    changes.lens.require(chain == '0x1', 'RPC endpoint is not Ethereum mainnet')
    block_hash = measured['block_hash']
    block = rpc(endpoint, 'eth_getBlockByHash', [block_hash, False], 2, deadline)
    changes.lens.require(isinstance(block, dict) and block.get('hash') == block_hash,
                         'RPC did not return the evidence block by hash')
    changes.lens.require(int(block['number'], 16) == measured['block_number'],
                         'evidence block number and hash disagree')
    rows = []
    for index, spender in enumerate(spenders, 3):
        code = rpc(endpoint, 'eth_getCode',
                   [spender, {'blockHash': block_hash, 'requireCanonical': True}],
                   index, deadline)
        changes.lens.require(isinstance(code, str) and code.startswith('0x')
                             and len(code) % 2 == 0,
                             'eth_getCode returned malformed bytecode')
        try:
            bytecode = bytes.fromhex(code[2:])
        except ValueError as exc:
            raise ValueError('eth_getCode returned non-hex bytecode') from exc
        rows.append({
            'spender': spender,
            'classification': 'runtime_code_present' if bytecode else 'no_runtime_code_at_block',
            'runtime_code_bytes': len(bytecode),
            'runtime_code_sha256': hashlib.sha256(bytecode).hexdigest(),
            'block_hash': block_hash,
        })
    return {
        'schema': 'active-allowance-spender-code-v1',
        'source': endpoint,
        'chain_id': 1,
        'token': measured['token'],
        'token_address': measured['token_address'],
        'block_number': measured['block_number'],
        'block_hash': block_hash,
        'measured_pair_count': len(measured['pairs']),
        'active_spender_count': len(spenders),
        'spenders': rows,
        'limitations': [
            'Runtime code is read for active spenders at the exact evidence block hash; RPC is trusted, not a proof.',
            'No runtime code does not prove an address is an EOA or safe; it may still be a precompile or future target.',
            'Code presence does not identify a controller, source, proxy implementation, or behavior.',
            'Only the supplied standard ERC-20 owner-spender observations are covered; this is not a full wallet audit.',
            'No wallet, key, secret, environment variable, signing, transaction, payment or write call is used.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation', help='workspace Allowance Lens or Changes JSON evidence')
    parser.add_argument('--endpoint', default=ENDPOINTS[0], help='public Ethereum RPC endpoint')
    parser.add_argument('--timeout', type=float, default=25, help='total deadline in seconds')
    args = parser.parse_args(argv)
    try:
        observation = changes.load(args.observation or DEFAULT_OBSERVATION)
        measured, spenders = active_spenders(observation)
        print(json.dumps(inspect(measured, spenders, args.endpoint, args.timeout), indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
