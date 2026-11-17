import collections
import unittest
import tailcache12_service_geometry as geometry
import tailcache12_service_campaign as core


class GeometryTest(unittest.TestCase):
    def test_fixed_equal_geometry_combinations_and_actual_cli_arguments(self):
        rows=geometry.schedule()
        self.assertEqual(rows,geometry.schedule())
        self.assertEqual(len(rows),8)
        self.assertEqual(len({r['label'] for r in rows}),8)
        grouped=collections.defaultdict(list)
        for row in rows:
            self.assertEqual((row['payload'],row['liveMiB'],row['qps'],row['seed']),(4096,0,50000,24301))
            self.assertEqual(row['extraArgs'],['--trace-pattern',row['tracePattern']])
            grouped[row['tracePattern'],row['block']].append(row)
        self.assertEqual(len(grouped),4)
        for pair in grouped.values():self.assertEqual({r['backend'] for r in pair},set(core.BACKENDS))


if __name__=='__main__':unittest.main()
