import copy
import math
import unittest
from transport.core import simulate


def config(flow=1, source=(0, 0), volumes=((20, 10), (15, 15)), times=(0, 5)):
    h = dict(nodes=[dict(id='a', storage_area_m2=1), dict(id='b', storage_area_m2=1)],
             edges=[{'id': 'e', 'from': 'a', 'to': 'b'}],
             node_ids=['a', 'b'], edge_ids=['e'], external_flows_m3_s=list(source),
             samples=[dict(time_s=t, volumes_m3=list(v), flows_m3_s=[999],
                           preceding_interval_mean_flows_m3_s=[flow])
                      for t, v in zip(times, volumes)])
    return dict(model='chemical', hydraulic_result=h, initial_concentration=[1, 0], dt_max_s=.1)


class CouplingTests(unittest.TestCase):
    def test_closed_conservation_and_storage(self):
        for model in ('chemical', 'biological'):
            c = config(); c['model'] = model
            r = simulate(c)
            self.assertAlmostEqual(sum(r['water_mass']), 20)
            self.assertAlmostEqual(r['mass_budget']['residual'], 0, places=10)
            self.assertAlmostEqual(r['water_budget']['residual_m3'], 0, places=10)
            for volume in r['volumes_m3']:
                self.assertAlmostEqual(volume, 15)
            self.assertAlmostEqual(r['concentration'][0], 1)
            self.assertAlmostEqual(r['concentration'][1], 1/3)

    def test_external_inflow_outflow_and_analytical_convergence(self):
        c = config(source=(1, -1), volumes=((20, 10), (20, 10)))
        c.update(initial_concentration=[0, 0], boundary_concentration=[1, 0])
        errors = []
        for dt in (1, .5, .25):
            c['dt_max_s'] = dt
            r = simulate(c)
            errors.append(abs(r['concentration'][0] - (1 - math.exp(-5/20))))
            self.assertGreater(r['mass_budget']['boundary_input'], 0)
            self.assertGreater(r['mass_budget']['boundary_export'], 0)
            self.assertAlmostEqual(r['mass_budget']['residual'], 0, places=10)
        self.assertLess(errors[1], errors[0] * .55)
        self.assertLess(errors[2], errors[1] * .55)

    def test_reverse_flow_and_interval_joins(self):
        c = config(flow=-1, volumes=((20, 10), (22, 8), (25, 5)), times=(0, 2, 5))
        c['initial_concentration'] = [0, 1]
        r = simulate(c)
        self.assertAlmostEqual(r['water_mass'][0], 5)
        self.assertAlmostEqual(r['water_mass'][1], 5)
        self.assertEqual([s['time_s'] for s in r['snapshots']], [0, 2, 5])
        self.assertAlmostEqual(r['mass_budget']['residual'], 0, places=10)

    def test_inconsistent_storage_rejected(self):
        c = config(volumes=((20, 10), (16, 14)))
        with self.assertRaisesRegex(ValueError, 'water balance'):
            simulate(c)

    def test_mean_flows_required_and_no_mutation(self):
        c = config(); before = copy.deepcopy(c)
        simulate(c)
        self.assertEqual(c, before)
        del c['hydraulic_result']['samples'][1]['preceding_interval_mean_flows_m3_s']
        with self.assertRaises(KeyError):
            simulate(c)

    def test_step_limit_is_aggregate(self):
        c = config(flow=-1, volumes=((20, 10), (22, 8), (25, 5)), times=(0, 2, 5))
        c['max_steps'] = 30
        with self.assertRaisesRegex(ValueError, '[Ss]tep limit'):
            simulate(c)


if __name__ == '__main__':
    unittest.main()
