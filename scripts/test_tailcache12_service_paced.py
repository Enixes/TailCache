import collections
import unittest

import tailcache12_service_campaign as core
import tailcache12_service_paced as paced


class PacedDesignTest(unittest.TestCase):
    def test_fixed_budget_and_equal_arrival_pairs(self):
        slots = paced.schedule()
        self.assertEqual(len(slots), 24)
        self.assertEqual(len({s['label'] for s in slots}), 24)
        self.assertEqual(slots, paced.schedule())
        grouped = collections.defaultdict(list)
        for s in slots:
            self.assertEqual((s['stage'], s['regime'], s['qps'], s['seed']),
                             ('paced-load', 'arrival', 50000, 24301))
            grouped[s['payload'], s['liveMiB'], s['block']].append(s)
        self.assertEqual(len(grouped), 12)
        for pair in grouped.values():
            self.assertEqual({s['backend'] for s in pair}, set(core.BACKENDS))
        self.assertEqual({s['payload'] for s in slots}, {256, 4096})
        self.assertEqual({s['liveMiB'] for s in slots}, {0, 208, 336})

    def test_prospective_protocols_are_in_frozen_source_map(self):
        paths = {str(p.relative_to(core.ROOT)) for p in core.source_files()}
        for name in ('PACED', 'OBSERVER'):
            self.assertIn('docs/TAILCACHE_SERVICE_' + name + '_PROTOCOL.md', paths)


if __name__ == '__main__':
    unittest.main()
