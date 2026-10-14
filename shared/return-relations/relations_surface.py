#!/usr/bin/env python3
"""Join integer relation review with fresh same-block code/call evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import return_relations as relations
sys.path.insert(0, str(HERE.parent / 'set-expiry'))
spec = importlib.util.spec_from_file_location('relations_fresh_surface', HERE.parent / 'set-expiry/fresh_surface.py')
fresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh)
SCHEMA = 'relations-surface-context-v1'
LIMITS = ('Historical independent call returns remain provider claims. Code proofs bind '
          'to supplied headers, not authenticated consensus. Signatures, integer types, '
          'units, review time and relations are reviewer choices. Structural selector '
          'evidence does not prove behavior. No current state, authority, future execution '
          'or stateful sequence is established. Nothing is signed or sent.')


def evaluate(evidence, policy, guard, choices, proofs, anchor_hash=None):
    selected = relations.guard(guard)
    wanted = relations.expiry.policy(policy)
    require = relations.core.require
    ids = {item['id'] for item in wanted['plan']['calls']}
    require(isinstance(choices, dict) and set(choices) == ids,
            'decoder choices must cover every planned member')
    # A relation may cover a subset, but its integer interpretation must equal
    # the code/call decoder's interpretation for every participating member.
    for layout in selected['layouts']:
        require(layout['id'] in choices and
                choices[layout['id']].get('return_types') == layout['types'],
                'relation layout differs from code/call decoder layout')
    result = {'schema': SCHEMA, 'verdict': 'withheld', 'reason': '',
              'input_sha256': {'policy': relations.binding.digest(wanted),
                               'guard': relations.binding.digest(selected),
                               'evidence': relations.binding.digest(evidence),
                               'choices': relations.binding.digest(choices),
                               'proofs': relations.binding.digest(proofs),
                               'anchor': relations.binding.digest(anchor_hash)},
              'relation_check': None, 'code_context': None,
              'decoded_calls': None, 'relations': None, 'limits': LIMITS}
    checked = relations.evaluate(evidence, wanted, selected)
    result['relation_check'] = {k: checked[k] for k in ('verdict', 'reason', 'policy_sha256', 'guard_sha256')}
    if checked['verdict'] != 'consistent':
        result['reason'] = 'Relation gate is ' + checked['verdict'] + '; code join skipped.'
        return result
    joined = fresh.evaluate(evidence, wanted, choices, proofs, anchor_hash)
    # Keep diagnosis without leaking partially accepted decoded values.
    result['code_context'] = {'verdict': joined['verdict'], 'reason': joined['reason'],
                              'input_sha256': joined['input_sha256']}
    if joined['surface_context'] is not None:
        result['code_context']['code_checks'] = joined['surface_context']['code_checks']
    if joined['verdict'] != 'aligned':
        result['reason'] = 'Code/call context did not align; all values and relations withheld.'
        return result
    result.update(verdict='consistent', reason='Complete fresh code/call set and every declared integer relation agree.',
                  decoded_calls=joined['decoded_calls'], relations=checked['checks'])
    relations.expiry.sets.bounded(result)
    return result


def demo_inputs():
    evidence, policy, guard = relations.demo_inputs()
    # Actual historical evidence and proof are reused unchanged. Their different
    # heights intentionally demonstrate refusal; no block or caller is invented.
    read = relations.binding.read_json
    proof = read(HERE.parent / 'surface-return/zto-proof.json')
    imd = read(HERE.parents[1] / 'line-3/tools/code-routes/imd-proof.json')
    choices, proofs = {}, {}
    for item in policy['plan']['calls']:
        choices[item['id']] = {'signature': 'balanceOf(address)' if 'balance' in item['id'] else 'totalSupply()',
                               'return_types': ['uint256']}
        proofs[item['id']] = imd if item['call']['to'] == relations.core.TOKENS['IMD'] else proof
    return evidence, policy, guard, choices, proofs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('demo', help='real historical evidence; different-block proofs must be withheld (exit 2)')
    check = sub.add_parser('check')
    for name in ('evidence', 'policy', 'guard', 'manifest'):
        check.add_argument(name)
    check.add_argument('--anchor-hash')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            inputs, anchor = demo_inputs(), None
        else:
            read = relations.binding.read_json
            choices, proofs = fresh.surface.manifest(read(args.manifest))
            inputs = (read(args.evidence), read(args.policy), read(args.guard), choices, proofs)
            anchor = args.anchor_hash
        result = evaluate(*inputs, anchor_hash=anchor)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['verdict'] == 'consistent' else 2
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError,
            IndexError, RecursionError, relations.core.RPCError) as exc:
        print(json.dumps({'schema': SCHEMA, 'verdict': 'invalid', 'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
