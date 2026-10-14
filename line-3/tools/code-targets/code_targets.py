#!/usr/bin/env python3
"""Inventory every decoded external-call operand in proved historical code."""
import argparse
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / 'code-calls'))
import code_calls as calls


def inventory(code):
    """Byte analysis only. Never interprets a constant as verified target code."""
    summary = calls.scan(code)
    pcs = [pc for pc, opcode, _, _ in calls.surface.instructions(code)
           if opcode in calls.CALLS]
    sites = []
    # Reuse full-runtime stack semantics; never slice/rebase PC or CODESIZE.
    for start in range(0, len(pcs), 32):
        selected = pcs[start:start + 32]
        batch = calls.scan(code, selected)['queried_calls']
        calls.lens.require(all(hit is not None and hit['pc'] == pc
                               for hit, pc in zip(batch, selected)), 'decoder disagreement')
        sites.extend(batch)
    calls.lens.require(len(sites) == summary['call_instruction_count'], 'incomplete call inventory')
    groups = {}
    unresolved = []
    for site in sites:
        if site['target_address'] is None:
            unresolved.append(site)
        else:
            groups.setdefault(site['target_address'], []).append(site)
    return {'call_instruction_count': len(sites),
            'locally_constant_target_count': sum(len(group) for group in groups.values()),
            'unresolved_target_count': len(unresolved),
            'distinct_constant_address_count': len(groups),
            'all_decoded_calls_included': True,
            'recognized_solidity_metadata': summary['recognized_solidity_metadata'],
            'constant_targets': [{'address': address, 'call_site_count': len(group),
                                  'opcodes': sorted({site['opcode'] for site in group}),
                                  'sites': group} for address, group in sorted(groups.items())],
            'unresolved_sites': unresolved}


def inspect(bundle, anchor_hash=None):
    verified = calls.proof.verify(bundle, anchor_hash)
    runtimes, seen = [], {}
    for node in bundle['observation']['nodes']:
        for item, role in ((node, 'candidate-path'), (node.get('beacon'), 'beacon')):
            if item is None:
                continue
            address = calls.lens.address(item['address'])
            code = calls.lens.code_bytes(item['code'])
            if address in seen:
                calls.lens.require(seen[address][0] == code, 'conflicting runtime')
                if role not in seen[address][1]['roles']:
                    seen[address][1]['roles'].append(role)
                continue
            result = {'address': address, 'code_hash': calls.lens.digest(code),
                      'runtime_bytes': len(code), 'roles': [role], **inventory(code)}
            seen[address] = (code, result)
            runtimes.append(result)
    return {'schema': 'code-targets-result-v1', 'chain_id': 1, 'target': verified['target'],
            'code_block': calls.ancestry.block_identity(bundle['observation']['block']),
            'proof': verified, 'runtimes': runtimes,
            'external_target_code_verified': False, 'dependency_completeness_verified': False,
            'reachability_verified': False, 'anchor_authenticity_verified': False,
            'semantic_safety_verified': False,
            'scope': 'Every decoded CALL/CALLCODE/DELEGATECALL/STATICCALL in each proved '
                     'historical runtime, grouped by locally constant low-160-bit target. '
                     'Full operand words and unresolved sites remain visible; metadata is included. '
                     'Constants are conditional on successful linear-segment execution. '
                     'This is no execution, target-account proof, complete dependency graph, '
                     'current-state, source-equivalence, consensus, finality, safety or transaction approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--anchor-hash')
    args = parser.parse_args()
    try:
        result = inspect(calls.ancestry.read_json(args.bundle), args.anchor_hash)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError, AttributeError,
            IndexError, RecursionError) as error:
        print('Code Targets: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
