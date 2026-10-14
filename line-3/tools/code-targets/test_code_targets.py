"""Proof refusal and complete-call inventory tests; synthetic code is test data only."""
import copy
import json
import importlib.util
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch
import code_targets as tool

FOLDER = Path(__file__).resolve().parent


def evidence(token='imd'):
    return tool.calls.ancestry.read_json(FOLDER.parent / 'code-routes' / (token + '-proof.json'))


def sites(result):
    return sorted([site for group in result['constant_targets'] for site in group['sites']]
                  + result['unresolved_sites'], key=lambda site: site['pc'])


class TargetsTests(unittest.TestCase):
    def test_real_offline_demo(self):
        spec = importlib.util.spec_from_file_location("targets_demo", FOLDER / "demo.py")
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            result = demo.main()
        self.assertTrue(result['demonstration_passed'])
        runtime = result['results'][1]['result']['runtimes'][0]
        self.assertEqual(runtime['unresolved_target_count'], 11)
        self.assertEqual(runtime['constant_targets'][0]['address'],
                         '0x1a44076050125825900e736c501f859c50fe728c')
        self.assertTrue(any(site['overlaps_recognized_metadata'] for site in sites(runtime)))

    def test_every_call_beyond_preview(self):
        code = bytes.fromhex('60015afa50') * 100 + bytes.fromhex('385afa')
        result = tool.inventory(code)
        self.assertEqual(result['call_instruction_count'], 101)
        self.assertEqual(result['locally_constant_target_count'], 101)
        self.assertEqual(result['constant_targets'][0]['call_site_count'], 100)
        last = sites(result)[-1]
        self.assertEqual(int(last['target_word'], 16), len(code))
        self.assertEqual(last['pc'], len(code) - 1)
        self.assertEqual(sites(result)[:64], tool.calls.scan(code)['call_preview'])

    def test_pc_semantics_preserved(self):
        code = b'\x5b' * 200 + bytes.fromhex('585afa')
        self.assertEqual(int(sites(tool.inventory(code))[0]['target_word'], 16), 200)

    def test_push_data_not_calls(self):
        result = tool.inventory(bytes.fromhex('63f1f2f4fa00'))
        self.assertEqual(result['call_instruction_count'], 0)
        self.assertEqual(result['constant_targets'], [])
        self.assertEqual(result['unresolved_sites'], [])

    def test_unresolved_including_after_stop(self):
        result = tool.inventory(bytes.fromhex('005afaf1f2f4'))
        self.assertEqual(result['unresolved_target_count'], 4)
        self.assertEqual([s['opcode'] for s in result['unresolved_sites']],
                         ['STATICCALL', 'CALL', 'CALLCODE', 'DELEGATECALL'])
        self.assertTrue(all(s['target_address'] is None for s in sites(result)))

    def test_zero_operand_is_not_filled_in(self):
        # Genuine measured zero operand is retained as evidence, not supplied as a missing address.
        result = tool.inventory(bytes.fromhex('5f5afa'))
        self.assertEqual(result['constant_targets'][0]['address'], '0x' + '00' * 20)
        self.assertEqual(result['unresolved_target_count'], 0)

    def test_low160_grouping_retains_full_words(self):
        word = (1 << 200) + 7
        code = b'\x7f' + word.to_bytes(32, 'big') + bytes.fromhex('5afa50') + bytes.fromhex('60075af4')
        group = tool.inventory(code)['constant_targets'][0]
        self.assertEqual(group['call_site_count'], 2)
        self.assertEqual(group['opcodes'], ['DELEGATECALL', 'STATICCALL'])
        self.assertEqual([int(s['target_word'], 16) for s in group['sites']], [word, 7])

    def test_sorted_addresses_and_ascending_sites(self):
        code = bytes.fromhex('60035afa5060015afa5060035afa')
        result = tool.inventory(code)
        self.assertEqual([int(g['address'], 16) for g in result['constant_targets']], [1, 3])
        self.assertEqual([s['pc'] for s in result['constant_targets'][1]['sites']], [3, 13])

    def test_input_and_output_independent(self):
        bundle = evidence()
        original = copy.deepcopy(bundle)
        result = tool.inspect(bundle)
        self.assertEqual(bundle, original)
        result['runtimes'][0]['roles'].append('changed')
        self.assertEqual(bundle, original)

    def test_invalid_proofs_before_inventory(self):
        for mutation in ('header', 'proof', 'runtime'):
            bundle = evidence()
            if mutation == 'header':
                bundle['header_rlp'] = bundle['header_rlp'][:-2] + 'ff'
            elif mutation == 'proof':
                bundle['proofs'][0]['accountProof'].pop()
            else:
                bundle['observation']['nodes'][0]['code'] = '0x00'
            with patch.object(tool, 'inventory', side_effect=AssertionError('analysis before verification')):
                with self.assertRaises(ValueError):
                    tool.inspect(bundle)

    def test_anchor_binding_and_limits(self):
        bundle = evidence()
        with self.assertRaises(ValueError):
            tool.inspect(bundle, '0x' + '11' * 32)
        result = tool.inspect(bundle, bundle['observation']['block']['hash'])
        self.assertEqual(result['proof']['anchor'], 'caller-supplied-block-hash')
        for field in ('external_target_code_verified', 'dependency_completeness_verified',
                      'reachability_verified', 'anchor_authenticity_verified', 'semantic_safety_verified'):
            self.assertFalse(result[field])

    def test_runtime_refusals(self):
        for code in (b'', b'\0' * 24577, b'\xef\x01\0', '00', bytearray(b'\0')):
            with self.assertRaises(ValueError):
                tool.inventory(code)
        self.assertEqual(tool.inventory(b'\0' * 24576)['call_instruction_count'], 0)

    def test_random_generated_calls_independent_oracle(self):
        rng = random.Random(36)
        for _ in range(60):
            code = bytearray()
            expected = []
            for _ in range(rng.randrange(1, 100)):
                # JUMPDEST resets knowledge; PUSH32 may contain any apparent opcode.
                code.append(0x5b)
                target = rng.getrandbits(256)
                code.append(0x7f)
                code.extend(target.to_bytes(32, 'big'))
                code.append(0x5a)
                pc = len(code)
                op = rng.choice(list(tool.calls.CALLS))
                code.append(op)
                expected.append((pc, target, op))
            result = tool.inventory(bytes(code))
            observed = sites(result)
            self.assertEqual(len(observed), len(expected))
            for site, (pc, word, op) in zip(observed, expected):
                self.assertEqual(site['pc'], pc)
                self.assertEqual(int(site['target_word'], 16), word)
                self.assertEqual(int(site['target_address'], 16), word & ((1 << 160) - 1))
                self.assertEqual(site['opcode'], tool.calls.CALLS[op][0])

    def test_cli_success_refusal_and_no_writes(self):
        command = [sys.executable, '-B', str(FOLDER / 'code_targets.py'), '--bundle',
                   str(FOLDER.parent / 'code-routes/imd-proof.json')]
        before = sorted(str(p) for p in FOLDER.rglob('*'))
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['runtimes'][0]['call_instruction_count'], 12)
        result = subprocess.run(command + ['--anchor-hash', 'bad'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(before, sorted(str(p) for p in FOLDER.rglob('*')))


if __name__ == '__main__':
    unittest.main()
