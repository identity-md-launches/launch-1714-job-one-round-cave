"""Replay real ZTO-first and IMD-second evidence offline."""
import json
from pathlib import Path
import code_targets as tool


def main():
    results = []
    for token in ('zto', 'imd'):
        bundle = tool.calls.ancestry.read_json(
            Path(__file__).resolve().parents[1] / 'code-routes' / (token + '-proof.json'))
        results.append({'token': token.upper(), 'result': tool.inspect(bundle)})
    zto, imd = [item['result']['runtimes'][0] for item in results]
    passed = (zto['call_instruction_count'] == 0 and imd['call_instruction_count'] == 12
              and all(item['result']['proof']['state_inclusion_verified'] for item in results)
              and all(runtime['call_instruction_count'] == runtime['locally_constant_target_count']
                      + runtime['unresolved_target_count'] for item in results
                      for runtime in item['result']['runtimes']))
    return {'demonstration_passed': passed, 'results': results,
            'note': 'Historical raw-proof replay, no new capture or independent anchor claimed.'}


if __name__ == '__main__':
    result = main()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['demonstration_passed'] else 1)
