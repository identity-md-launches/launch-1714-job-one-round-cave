#!/usr/bin/env python3
"""Compare two pinned, read-only ZTO/IMD pool captures before releasing a bound."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'zto-path'))
import zto_path as path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / 'zto-path' / 'observation.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def state_view(observation):
    """Keep pool evidence and omit only the transport label."""
    path.decode(observation)
    base = dict(observation['base'])
    base.pop('source', None)
    return {'schema': observation['schema'], 'base': base,
            'word_radius': observation['word_radius'],
            'bitmap': observation['bitmap'], 'ticks': observation['ticks']}


def compare_snapshots(first, second):
    left, right = state_view(first), state_view(second)
    same_block = (left['base']['block']['number'] == right['base']['block']['number'] and
                  left['base']['block']['hash'] == right['base']['block']['hash'])
    same_state = same_block and canonical(left) == canonical(right)
    digest = hashlib.sha256(canonical(left)).hexdigest()
    return {'same_block': same_block, 'same_pool_state_and_coverage': same_state,
            'first_state_sha256': digest,
            'second_state_sha256': hashlib.sha256(canonical(right)).hexdigest()}


def _quoter_output(check, observation, token, amount, expected_output):
    path.z.require(isinstance(check, dict) and check.get('schema') == 'zto-path-quoter-check-v1',
                   'unexpected quoter check schema')
    path.z.require(len(check.get('results', [])) == 1, 'expected one quoter result per source')
    result = check['results'][0]
    actual = str(path.z.words(result['raw_result'], 2)[0])
    matches = (check.get('all_match') is True and check.get('block') == observation['base']['block'] and
               result.get('input_token') == token and result.get('amount') == amount and
               result.get('local_output_raw') == expected_output and result.get('matches') is True and
               actual == expected_output)
    return actual, matches


def corroborate(first, second, check_a, check_b, token, amount, slippage_bps):
    path.z.require(token in ('ZTO', 'IMD'), 'input must be ZTO or IMD')
    path.z.require(type(slippage_bps) is int and 0 <= slippage_bps <= 9999,
                   'slippage bps must be 0..9999')
    comparison = compare_snapshots(first, second)
    quote_a = path.quote(first, token, amount)
    quote_b = path.quote(second, token, amount)
    local_complete = quote_a['status'] == quote_b['status'] == 'estimated'
    local_same = (local_complete and int(quote_a['estimate']['output_raw']) > 0 and
                  quote_a['estimate']['output_raw'] == quote_b['estimate']['output_raw'] and
                  quote_a['requested_input_raw'] == quote_b['requested_input_raw'])
    expected_output = quote_a.get('estimate', {}).get('output_raw')
    output_a, check_a_matches = _quoter_output(check_a, first, token, amount, expected_output)
    output_b, check_b_matches = _quoter_output(check_b, second, token, amount, expected_output)
    state_matches = comparison['same_pool_state_and_coverage']
    quote_matches = output_a == output_b == expected_output
    released = (state_matches and local_same and check_a_matches and check_b_matches and quote_matches)
    minimum_raw = None
    if released:
        minimum_raw = str(int(quote_a['estimate']['output_raw']) * (10000-slippage_bps) // 10000)
    return {
        'schema': 'zto-witness-report-v1',
        'status': 'corroborated' if released else 'withheld',
        'pool_id': path.z.POOL,
        'block': first['base']['block'],
        'input_token': token,
        'output_token': 'IMD' if token == 'ZTO' else 'ZTO',
        'requested_input': amount,
        'checks': {
            **comparison,
            'both_local_fills_complete_and_equal': local_same,
            'first_quoter_matches_local': check_a_matches,
            'second_quoter_matches_local': check_b_matches,
            'quoter_outputs_equal_local_estimate': quote_matches,
        },
        'bound_released': released,
        'bound': ({'estimated_output_raw': quote_a['estimate']['output_raw'],
                   'planning_minimum_raw': minimum_raw,
                   'slippage_bps': slippage_bps} if released else None),
        'source_labels': [first['base']['source'], second['base']['source']],
        'limitations': [
            'Different endpoint URLs do not prove different upstream providers or independent trust.',
            'The planning minimum is arithmetic only; it is not enforced by a router or receipt.',
            'No token settlement behavior, gas, MEV, future liquidity, wallet or transaction is modeled.'
        ]
    }


def demo():
    """Exercise validation against one real capture while refusing false corroboration."""
    observation = path.read_json(str(FIXTURE))
    state, _, _ = path.decode(observation)
    estimate = path.quote(observation, 'ZTO', '1')
    return {
        'schema': 'zto-witness-demo-v1',
        'mode': 'single_source_historical_fixture',
        'pool_id': path.z.POOL,
        'block': observation['base']['block'],
        'source': observation['base']['source'],
        'active_liquidity_raw': str(state['liquidity']),
        'one_zto_local_quote': estimate.get('estimate', {}).get('output'),
        'local_quote_status': estimate['status'],
        'bound_released': False,
        'reason': 'One saved endpoint capture cannot satisfy the two-source witness gate.',
        'limitations': ['Historical fixture: no fresh RPC calls and no second source are claimed.']
    }


def live(args):
    tag = args.block if args.block in ('finalized', 'safe', 'latest') else hex(int(args.block))
    first = path.capture(args.rpc_a, tag, args.word_radius)
    # Pin source B to source A's exact height, then require its hash to agree.
    block_number = int(first['base']['block']['number'], 16)
    second = path.capture(args.rpc_b, hex(block_number), args.word_radius)
    cases = [(args.input, args.amount)]
    check_a = path.compare(first, args.rpc_a, cases)
    check_b = path.compare(second, args.rpc_b, cases)
    return corroborate(first, second, check_a, check_b, args.input, args.amount,
                       args.slippage_bps)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--demo', action='store_true', help='offline, single-source refusal demonstration')
    mode.add_argument('--live', action='store_true', help='read both explicit RPC endpoints')
    parser.add_argument('--rpc-a', default=path.z.PUBLIC_RPC)
    parser.add_argument('--rpc-b', default='https://eth.drpc.org')
    parser.add_argument('--block', default='finalized')
    parser.add_argument('--word-radius', type=int, default=1)
    parser.add_argument('--input', choices=('ZTO', 'IMD'), default='ZTO')
    parser.add_argument('--amount', default='1')
    parser.add_argument('--slippage-bps', type=int, default=100)
    parser.add_argument('--save-report', help='write JSON report inside this workspace')
    args = parser.parse_args(argv)
    try:
        path.z.require(not args.demo or not args.save_report,
                       'offline demo does not save a report; redirect stdout if needed')
        if args.live:
            path.z.require(args.rpc_a != args.rpc_b, 'supply two distinct endpoint URLs')
            result = live(args)
        else:
            result = demo()
        if args.save_report:
            path.save_json(args.save_report, result)
        print(json.dumps(result, indent=2))
        return 0 if result.get('bound_released') or result.get('mode') == 'single_source_historical_fixture' else 2
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
