import copy
import json
from pathlib import Path
import unittest

import zto_witness as witness

HERE = Path(__file__).resolve().parent
OBSERVATION = json.loads((HERE.parent / 'zto-path' / 'observation.json').read_text())
QUOTER = json.loads((HERE.parent / 'zto-path' / 'quoter-check.json').read_text())


def one_zto_check():
    result = next(row for row in QUOTER['results'] if row['input_token'] == 'ZTO' and row['amount'] == '1')
    return {'schema': QUOTER['schema'], 'all_match': True, 'block': QUOTER['block'],
            'results': [result]}


class WitnessTests(unittest.TestCase):
    def setUp(self):
        self.first = copy.deepcopy(OBSERVATION)
        self.second = copy.deepcopy(OBSERVATION)
        self.second['base']['source'] = 'https://other.example/rpc'
        self.check = one_zto_check()

    def test_source_label_is_ignored_but_pool_state_matches(self):
        comparison = witness.compare_snapshots(self.first, self.second)
        self.assertTrue(comparison['same_block'])
        self.assertTrue(comparison['same_pool_state_and_coverage'])
        self.assertEqual(comparison['first_state_sha256'], comparison['second_state_sha256'])

    def test_block_hash_mismatch_withholds(self):
        self.second['base']['block']['hash'] = '0x' + '00' * 32
        self.assertFalse(witness.compare_snapshots(self.first, self.second)['same_block'])
        report = witness.corroborate(self.first, self.second, self.check, self.check,
                                     'ZTO', '1', 100)
        self.assertEqual(report['status'], 'withheld')
        self.assertIsNone(report['bound'])

    def test_pool_state_change_withholds(self):
        liquidity = int(self.second['base']['raw']['liquidity'], 16)
        self.second['base']['raw']['liquidity'] = '0x' + format(liquidity + 1, '064x')
        report = witness.corroborate(self.first, self.second, self.check, self.check,
                                     'ZTO', '1', 100)
        self.assertFalse(report['checks']['same_pool_state_and_coverage'])
        self.assertFalse(report['bound_released'])

    def test_matching_state_and_both_quoter_checks_release_floor_bound(self):
        report = witness.corroborate(self.first, self.second, self.check, self.check,
                                     'ZTO', '1', 100)
        quote = witness.path.quote(self.first, 'ZTO', '1')
        expected = str(int(quote['estimate']['output_raw']) * 9900 // 10000)
        self.assertEqual(report['status'], 'corroborated')
        self.assertEqual(report['bound']['planning_minimum_raw'], expected)

    def test_failed_quoter_check_withholds(self):
        failed = dict(self.check, all_match=False)
        report = witness.corroborate(self.first, self.second, failed, self.check,
                                     'ZTO', '1', 100)
        self.assertFalse(report['bound_released'])
        self.assertIsNone(report['bound'])

    def test_demo_is_explicitly_single_source(self):
        report = witness.demo()
        self.assertEqual(report['mode'], 'single_source_historical_fixture')
        self.assertFalse(report['bound_released'])


if __name__ == '__main__':
    unittest.main()
