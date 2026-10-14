"""Check release boundaries using real historical evidence, without networking."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import relations_surface as tool


class RelationsSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.inputs = list(tool.demo_inputs())

    def check(self):
        return tool.evaluate(*self.inputs)

    def single_real_call(self):
        # An identity relation tests plumbing, not an economic cross-call claim.
        evidence, policy, choices, proofs = tool.fresh.demo_inputs()
        label = next(iter(choices))
        guard = {'schema': tool.relations.SCHEMA,
                 'policy_sha256': tool.relations.binding.digest(policy),
                 'layouts': [{'id': label, 'types': ['uint256'], 'unit': 'zto-base-units'}],
                 'relations': [{'id': 'identity', 'left': {'id': label, 'index': 0},
                                'op': 'eq', 'right': {'id': label, 'index': 0}}]}
        self.inputs = [evidence, policy, guard, choices, proofs]

    def test_real_different_block_refused_without_partial_values(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')):
            result = self.check()
        self.assertEqual(result['relation_check']['verdict'], 'consistent')
        self.assertEqual(result['verdict'], 'withheld')
        self.assertIsNone(result['decoded_calls'])
        self.assertIsNone(result['relations'])
        self.assertTrue(any(c['failed_checks'] for c in result['code_context']['code_checks']))

    def test_same_block_real_evidence_release_path(self):
        self.single_real_call()
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')):
            result = self.check()
        self.assertEqual(result['verdict'], 'consistent')
        self.assertEqual(len(result['decoded_calls']), 1)
        self.assertTrue(result['relations'][0]['passed'])

    def test_false_relation_skips_code_join(self):
        self.inputs[2]['relations'][0]['op'] = 'gt'
        with patch.object(tool.fresh, 'evaluate', side_effect=AssertionError('must skip')):
            result = self.check()
        self.assertEqual(result['verdict'], 'withheld')
        self.assertIsNone(result['code_context'])

    def test_guard_digest_mismatch_skips_code_join(self):
        self.inputs[2]['policy_sha256'] = '1' * 64
        with patch.object(tool.fresh, 'evaluate', side_effect=AssertionError('must skip')):
            result = self.check()
        self.assertEqual(result['relation_check']['verdict'], 'withheld')

    def test_layout_interpretations_must_match(self):
        self.inputs[3]['zto-manager-balance']['return_types'] = ['int256']
        with self.assertRaisesRegex(ValueError, 'layout differs'):
            self.check()

    def test_choices_must_cover_unrelated_member(self):
        del self.inputs[3]['imd-supply']
        with self.assertRaisesRegex(ValueError, 'every planned member'):
            self.check()

    def test_missing_unrelated_evidence_refuses_relations(self):
        self.inputs[0]['observations'] = [item for item in self.inputs[0]['observations'] if item['id'] != 'imd-supply']
        result = self.check()
        self.assertEqual(result['verdict'], 'withheld')
        self.assertIsNone(result['relations'])
        self.assertIsNone(result['code_context'])

    def test_expired_policy_refuses(self):
        policy = self.inputs[1]
        policy['as_of'] = hex(int(policy['plan']['block']['timestamp'],16) + policy['max_age_seconds'] + 1)
        self.inputs[2]['policy_sha256'] = tool.relations.binding.digest(policy)
        result = self.check()
        self.assertEqual(result['relation_check']['verdict'], 'withheld')
        self.assertIsNone(result['code_context'])

    def test_wrong_anchor_refuses(self):
        self.single_real_call()
        with self.assertRaises(ValueError):
            tool.evaluate(*self.inputs, anchor_hash='0x'+'11'*32)

    def test_corrupted_proof_cannot_release(self):
        self.single_real_call()
        proof = next(iter(self.inputs[4].values()))
        proof['header_rlp'] = '0x00'
        with self.assertRaises(ValueError):
            self.check()

    def test_input_immutability(self):
        old = copy.deepcopy(self.inputs)
        self.check()
        self.assertEqual(self.inputs, old)

    def test_cli_demo_expected_refusal(self):
        done = subprocess.run([sys.executable,'-B',str(Path(tool.__file__)),'demo'],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(done.returncode,2)
        result = json.loads(done.stdout)
        self.assertEqual(result['verdict'],'withheld')
        self.assertIsNone(result['decoded_calls'])


if __name__ == '__main__':
    unittest.main()
