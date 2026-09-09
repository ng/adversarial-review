#!/usr/bin/env python3
"""Resolve and validate frozen PR comparison scopes without running reviewers."""
import argparse
import concurrent.futures
from pathlib import Path
from run import ROOT, comparison_base, selected, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, default=ROOT / 'benchmarks/work')
    parser.add_argument('--benchmark', default='all')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    work = args.work_root.resolve()
    def resolve(case):
        try:
            base = comparison_base(work, case)
            result = {'status': 'validated', 'comparison_base': base,
                      'dataset_base': case['base'], 'input_hash': case['input_hash']}
        except Exception as exc:
            result = {'status': 'failed', 'error': str(exc), 'input_hash': case['input_hash']}
        write_json(work / 'scope-audit' / case['benchmark'] / (case['id'] + '.json'), result)
        print(case['benchmark'], case['id'], result['status'], result.get('error', ''), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(resolve, selected(work, args.benchmark, args.limit)))


if __name__ == '__main__':
    main()
