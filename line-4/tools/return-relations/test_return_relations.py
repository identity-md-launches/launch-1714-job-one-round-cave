"""Offline historical replay and refusal boundaries for relation review."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import return_relations as tool


class ReturnRelationsTests(unittest.TestCase):
    def setUp(self):
        self.evidence, self.policy, self.guard = tool.demo_inputs()

    def check(self):
        return tool.evaluate(self.evidence, self.policy, self.guard)

    def rebind(self):
        self.guard['policy_sha256'] = tool.binding.digest(tool.expiry.policy(self.policy))

    def synthetic(self, values, types):
        # Test-only payloads; never substitute these for real demonstration evidence.
        raw = '0x' + ''.join((v % 2**256).to_bytes(32, 'big').hex() for v in values)
        self.policy['plan']['calls'][1]['expected_return'] = raw
        observation = self.evidence['observations'][1]['observation']
        observation.update(returns='raw', outcome={'result': raw})
        self.guard['layouts'][0]['types'] = types
        self.rebind()

    def test_real_zto(self):
        result = self.check()
        self.assertEqual(result['verdict'], 'consistent')
        self.assertEqual(result['checks'][0]['left_value'], '304756253603277900345322340')
        self.assertEqual(result['checks'][0]['right_value'], '1000000000000000000000000000')
        self.assertEqual(result['block'], self.policy['plan']['block'])
        self.assertNotIn('unsigned_call', json.dumps(result))

    def test_all_operators(self):
        for op, expected in [('le', True), ('lt', True), ('eq', False),
                             ('ge', False), ('gt', False), ('ne', True)]:
            with self.subTest(op=op):
                self.guard['relations'][0]['op'] = op
                result = self.check()
                self.assertEqual(result['checks'][0]['passed'], expected)
                self.assertEqual(result['verdict'], 'consistent' if expected else 'withheld')

    def test_equality_and_inclusive_boundary(self):
        supply = int(self.policy['plan']['calls'][0]['expected_return'], 16)
        self.synthetic([supply], ['uint256'])
        for op, expected in [('eq', True), ('le', True), ('ge', True),
                             ('lt', False), ('gt', False), ('ne', False)]:
            self.guard['relations'][0]['op'] = op
            self.assertEqual(self.check()['checks'][0]['passed'], expected)

    def test_signed_and_tuple_index(self):
        self.synthetic([2**256 - 1, -128], ['uint256', 'int8'])
        self.guard['relations'][0]['left']['index'] = 1
        result = self.check()
        self.assertEqual(result['verdict'], 'consistent')
        self.assertEqual(result['checks'][0]['left_value'], '-128')
        self.guard['relations'][0]['left']['index'] = 0
        self.assertEqual(self.check()['verdict'], 'withheld')

    def test_every_relation_must_pass(self):
        second = copy.deepcopy(self.guard['relations'][0])
        second.update(id='strict-equality', op='eq')
        self.guard['relations'].append(second)
        result = self.check()
        self.assertEqual(result['verdict'], 'withheld')
        self.assertEqual([x['passed'] for x in result['checks']], [True, False])

    def test_policy_substitution(self):
        for change in ('age', 'time', 'caller', 'block', 'expected'):
            old = copy.deepcopy(self.policy)
            if change == 'age':
                self.policy['max_age_seconds'] += 1
            elif change == 'time':
                self.policy['as_of'] = hex(int(self.policy['as_of'], 16) + 1)
            elif change == 'caller':
                self.policy['plan']['calls'][0]['call']['from'] = tool.core.TOKENS['IMD']
            elif change == 'block':
                self.policy['plan']['block']['number'] = hex(int(self.policy['plan']['block']['number'], 16)+1)
            else:
                self.policy['plan']['calls'][2]['expected_return'] = '0x' + '01'*32
            result = self.check()
            self.assertEqual(result['verdict'], 'withheld')
            self.assertEqual(result['checks'], [])
            self.policy = old

    def test_expiry_and_future_review(self):
        ts = int(self.policy['plan']['block']['timestamp'], 16)
        self.policy['as_of'] = hex(ts + self.policy['max_age_seconds'] + 1)
        self.rebind()
        self.assertEqual(self.check()['verdict'], 'withheld')
        self.policy['as_of'] = hex(ts - 1)
        self.rebind()
        self.assertEqual(self.check()['verdict'], 'inconclusive')
        self.assertEqual(self.check()['decoded'], [])

    def test_missing_unreferenced_member(self):
        self.evidence['observations'].pop()
        result = self.check()
        self.assertEqual(result['verdict'], 'inconclusive')
        self.assertEqual(result['checks'], [])

    def test_changed_unreferenced_member(self):
        self.evidence['observations'][2]['observation']['outcome']['result'] = '0x'+'01'*32
        self.assertEqual(self.check()['verdict'], 'withheld')
        self.assertEqual(self.check()['decoded'], [])

    def test_missing_sender_and_revert(self):
        obs = self.evidence['observations'][0]['observation']
        del obs['call']['from']
        self.assertEqual(self.check()['verdict'], 'inconclusive')
        self.evidence, _, _ = tool.demo_inputs()
        self.evidence['observations'][0]['observation']['outcome'] = {
            'error': {'code': 3, 'message': 'execution reverted', 'data': '0x'}}
        self.assertEqual(self.check()['verdict'], 'withheld')

    def test_unknown_plan_member(self):
        self.guard['layouts'][0]['id'] = 'absent'
        self.guard['relations'][0]['left']['id'] = 'absent'
        self.assertEqual(self.check()['verdict'], 'withheld')

    def test_noncanonical_and_extra_return_bytes(self):
        for values, types in [([256], ['uint8']), ([128], ['int8']),
                              ([1, 2], ['uint256']), ([], ['uint256'])]:
            self.synthetic(values, types)
            result = self.check()
            self.assertEqual(result['verdict'], 'inconclusive')
            self.assertEqual(result['checks'], [])
            self.assertEqual(result['decoded'], [])

    def test_units_must_match(self):
        self.guard['layouts'][0]['unit'] = 'imd-base-units'
        with self.assertRaisesRegex(ValueError, 'same explicit unit'):
            self.check()

    def test_schema_and_layout_refusals(self):
        original = copy.deepcopy(self.guard)
        for field, value in [('schema', 'other'), ('policy_sha256', 'ab'),
                             ('layouts', []), ('relations', []), ('extra', True)]:
            self.guard = {**original, field: value}
            with self.assertRaises(ValueError):
                self.check()
        self.guard = copy.deepcopy(original)
        for types in [['bool'], ['uint'], ['uint7'], ['bytes32'], ['uint256[]'], []]:
            self.guard['layouts'][0]['types'] = types
            with self.assertRaises(ValueError):
                self.check()

    def test_references_and_operator_refusals(self):
        original = copy.deepcopy(self.guard)
        for bad in [-1, 1, True, '0', 0.0]:
            self.guard = copy.deepcopy(original)
            self.guard['relations'][0]['left']['index'] = bad
            with self.assertRaises(ValueError):
                self.check()
        for op in ['<=', 'eval', 1, []]:
            self.guard = copy.deepcopy(original)
            self.guard['relations'][0]['op'] = op
            with self.assertRaises(ValueError):
                self.check()
        self.guard = copy.deepcopy(original)
        self.guard['relations'][0]['left']['id'] = 'missing'
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_and_unused_layouts(self):
        original = copy.deepcopy(self.guard)
        self.guard['layouts'].append(copy.deepcopy(self.guard['layouts'][0]))
        with self.assertRaises(ValueError):
            self.check()
        self.guard = copy.deepcopy(original)
        self.guard['relations'].append(copy.deepcopy(self.guard['relations'][0]))
        with self.assertRaises(ValueError):
            self.check()
        self.guard = copy.deepcopy(original)
        self.guard['layouts'].append({'id': 'imd-supply', 'types': ['uint256'], 'unit': 'imd-base-units'})
        with self.assertRaises(ValueError):
            self.check()

    def test_immutable_inputs(self):
        before = copy.deepcopy((self.evidence, self.policy, self.guard))
        self.check()
        self.assertEqual(before, (self.evidence, self.policy, self.guard))

    def test_demo_offline(self):
        with patch.object(tool.core.RPC, 'call', side_effect=AssertionError('network forbidden')):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tool.main(['demo']), 0)
        self.assertEqual(json.loads(out.getvalue())['verdict'], 'consistent')

    def test_cli_exit_codes_and_duplicate_keys(self):
        scratch = Path('test/scratch'); scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            paths = [Path(temp)/f'{name}.json' for name in ('evidence', 'policy', 'guard')]
            for path, value in zip(paths, (self.evidence, self.policy, self.guard)):
                path.write_text(json.dumps(value))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(['check', *map(str, paths)]), 0)
            self.guard['relations'][0]['op'] = 'gt'
            paths[-1].write_text(json.dumps(self.guard))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(['check', *map(str, paths)]), 1)
            paths[-1].write_text('{"schema":"a","schema":"b"}')
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(tool.main(['check', *map(str, paths)]), 2)
            self.assertIn('duplicate JSON key', err.getvalue())


if __name__ == '__main__':
    unittest.main()
