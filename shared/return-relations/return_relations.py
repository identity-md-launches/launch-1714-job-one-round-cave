#!/usr/bin/env python3
"""Check integer relations across a complete historical independent-call set."""
import argparse
import importlib.util
import json
import operator
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent


def sibling(name, path):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


expiry = sibling('relations_expiry', 'set-expiry/set_expiry.py')
lens = sibling('relations_lens', 'return-bounds/return_lens.py')
binding, core = expiry.sets.binding, expiry.core
SCHEMA = 'rehearsal-return-relations-v1'
OPERATORS = {'le': operator.le, 'lt': operator.lt, 'eq': operator.eq,
             'ge': operator.ge, 'gt': operator.gt, 'ne': operator.ne}
EXIT = {'consistent': 0, 'withheld': 1, 'inconclusive': 2}
LIMITS = (
    'Relations compare raw integers under reviewer-declared ABI layouts and units; '
    'neither ABI nor economic meaning is authenticated. The full set must bind at '
    'one exact historical block within the explicit review-time policy. Review time '
    'is supplied, not a live clock. Provider claims and content digests do not prove '
    'chain authenticity or reviewer identity. Calls are independent, not a stateful '
    'sequence. No current state, future execution, authority, gas or state effects '
    'are established. No call is released, signed or sent.'
)


def guard(value):
    expiry.sets.bounded(value)
    core.require(isinstance(value, dict) and set(value) ==
                 {'schema', 'policy_sha256', 'layouts', 'relations'},
                 'guard requires exactly schema, policy_sha256, layouts and relations')
    core.require(value['schema'] == SCHEMA, 'unsupported relations schema')
    core.require(isinstance(value['policy_sha256'], str) and
                 re.fullmatch(r'[0-9a-f]{64}', value['policy_sha256']), 'invalid policy digest')
    layouts = []
    by_id = {}
    for item in expiry.sets.entries(value['layouts'], {'id', 'types', 'unit'}):
        types = lens.layout(item['types'])
        core.require(all(re.fullmatch(r'(?:uint|int)[0-9]+', t) for t in types),
                     'relations support explicit integer types only')
        unit = expiry.sets.identifier(item['unit'])
        by_id[item['id']] = {'types': types, 'unit': unit}
        layouts.append({'id': item['id'], 'types': types, 'unit': unit})

    def reference(ref):
        core.require(isinstance(ref, dict) and set(ref) == {'id', 'index'},
                     'reference requires exactly id and index')
        member = expiry.sets.identifier(ref['id'])
        core.require(member in by_id, 'reference has no declared layout')
        index = ref['index']
        core.require(type(index) is int and 0 <= index < len(by_id[member]['types']),
                     'reference index is outside the declared layout')
        return {'id': member, 'index': index}

    relations = []
    used = set()
    for item in expiry.sets.entries(value['relations'], {'id', 'left', 'op', 'right'}):
        core.require(isinstance(item['op'], str) and item['op'] in OPERATORS,
                     'operator must be le, lt, eq, ge, gt or ne')
        left, right = reference(item['left']), reference(item['right'])
        core.require(by_id[left['id']]['unit'] == by_id[right['id']]['unit'],
                     'both operands must have the same explicit unit label')
        used.update((left['id'], right['id']))
        relations.append({'id': item['id'], 'left': left, 'op': item['op'], 'right': right})
    core.require(used == set(by_id), 'every declared layout must participate in a relation')
    return {**value, 'layouts': layouts, 'relations': relations}


def evaluate(evidence, policy, selected_guard):
    chosen, policy = guard(selected_guard), expiry.policy(policy)
    report = {'schema': SCHEMA, 'verdict': 'inconclusive', 'reason': '',
              'policy_sha256': binding.digest(policy), 'guard_sha256': binding.digest(chosen),
              'checks': [], 'decoded': [], 'limits': LIMITS}
    if chosen['policy_sha256'] != report['policy_sha256']:
        report.update(verdict='withheld', reason='guard is bound to a different complete expiry policy')
        return report
    members = {item['id']: item for item in policy['plan']['calls']}
    if any(item['id'] not in members for item in chosen['layouts']):
        report.update(verdict='withheld', reason='declared layout member is absent from the reviewed plan')
        return report
    fresh = expiry.evaluate(evidence, policy)
    report['set_expiry'] = {'verdict': fresh['verdict'], 'reason': fresh['reason'],
                            'evidence_sha256': fresh['set_binding']['evidence_sha256']}
    if fresh['verdict'] != 'fresh':
        report.update(verdict=('inconclusive' if fresh['verdict'] == 'inconclusive' else 'withheld'),
                      reason='complete historical set check is ' + fresh['verdict'])
        return report
    decoded = {}
    try:
        for layout in chosen['layouts']:
            # Full set binding already verified actual bytes equal these exact bytes.
            values = lens.decode(members[layout['id']]['expected_return'], layout['types'])
            decoded[layout['id']] = values
    except ValueError as exc:
        report['reason'] = 'integer layout rejected: ' + str(exc)
        return report
    report['block'] = policy['plan']['block']
    report['decoded'] = [{'id': item['id'], 'unit': item['unit'],
                          'values': decoded[item['id']]} for item in chosen['layouts']]
    for relation in chosen['relations']:
        left, right = relation['left'], relation['right']
        a = decoded[left['id']][left['index']]['value']
        b = decoded[right['id']][right['index']]['value']
        report['checks'].append({**relation, 'left_value': a, 'right_value': b,
                                'passed': OPERATORS[relation['op']](int(a), int(b))})
    if all(item['passed'] for item in report['checks']):
        report.update(verdict='consistent', reason='complete historical set and every declared relation match')
    else:
        report.update(verdict='withheld', reason='at least one declared integer relation fails')
    return report


def demo_inputs():
    return (binding.read_json(HERE.parent / 'rehearsal-set/zto-set-evidence.json'),
            binding.read_json(HERE.parent / 'set-expiry/zto-set-expiry-policy.json'),
            binding.read_json(HERE / 'zto-relations-guard.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='compare real historical ZTO balance and total supply offline')
    check = commands.add_parser('check', help='check explicit evidence, expiry policy and relation guard')
    for key in ('evidence', 'policy', 'guard'):
        check.add_argument(key)
    args = parser.parse_args(argv)
    try:
        inputs = demo_inputs() if args.command == 'demo' else tuple(
            binding.read_json(getattr(args, key)) for key in ('evidence', 'policy', 'guard'))
        report = evaluate(*inputs)
        print(json.dumps(report, indent=2, allow_nan=False))
        return EXIT[report['verdict']]
    except (ValueError, KeyError, TypeError, OSError, RecursionError, core.RPCError) as exc:
        print(json.dumps({'schema': SCHEMA, 'verdict': 'inconclusive', 'error': str(exc)}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
