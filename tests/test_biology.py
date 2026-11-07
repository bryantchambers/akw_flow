import unittest
import numpy as np
from transport.biology import reaction_tendencies, get_preset, validate_parameters


class BiologyTests(unittest.TestCase):
    def rhs(self, p=None, env=None, water=None, bed=None):
        return reaction_tendencies([100., 200.] if water is None else water,
                                  [50., 20.] if bed is None else bed,
                                  [10., 20.], [5., 10.], p or {}, env or {})

    def test_disabled_zero_and_presets(self):
        for name in ('ecoli_indicator', 'cryptosporidium', 'giardia', 'b_subtilis_spore'):
            preset = get_preset(name)
            result = self.rhs(preset['parameters'])
            for key in ('water', 'bed', 'irreversible_loss', 'external_source'):
                np.testing.assert_array_equal(result[key], 0)
        self.assertEqual(get_preset('crypto')['engineered_uv_reference']['required_dose_j_m2'][3], 58.)

    def test_exchange_conserves_inventory(self):
        p = dict(settling_enabled=True, settling_velocity_m_s=.01,
                 particle_associated_fraction=.5, attachment_enabled=True,
                 attachment_s=.02, detachment_enabled=True, detachment_s=.03,
                 resuspension_enabled=True, resuspension_s=.04, critical_shear_pa=1.)
        r = self.rhs(p, {'bed_shear_pa': [0., 2.]})
        np.testing.assert_allclose(r['water'] + r['bed'], 0)
        np.testing.assert_allclose(r['settling_transfer'], [.25, .5])
        np.testing.assert_allclose(r['resuspension_transfer'], [0., .8])
        np.testing.assert_array_equal(r['irreversible_loss'], 0)

    def test_viability_budget_and_temperature(self):
        p = dict(dark_enabled=True, dark_water_s=.001, dark_bed_s=.002,
                 q10=2., reference_temperature_c=20., temperature_min_c=0., temperature_max_c=40.,
                 solar_enabled=True, solar_coefficient_m2_j=.0001,
                 light_attenuation_m=0., solar_shielded_fraction=.2,
                 uv_enabled=True, uv_coefficient_m2_j=.0002)
        r = self.rhs(p, {'temperature_c':[20.,30.], 'solar_irradiance_w_m2':10.,
                         'depth_m':2., 'uv_fluence_rate_w_m2':5.})
        np.testing.assert_allclose(r['dark_water_loss'], [.1,.4])
        np.testing.assert_allclose(r['solar_water_loss'], [.08,.16])
        np.testing.assert_allclose(r['water']+r['bed'], -r['irreversible_loss'])
        self.assertTrue(np.all(r['water'] < 0))
        with self.assertRaises(ValueError):
            self.rhs(p, {'temperature_c':50.})

    def test_growth_requires_eligibility_and_capacity(self):
        p=dict(growth_enabled=True, growth_s=.01, carrying_capacity_count_m3=20.)
        with self.assertRaises(ValueError): self.rhs(p)
        p['growth_permitted']=True
        r=self.rhs(p, water=[100.,500.])
        np.testing.assert_allclose(r['external_source'], [.5,0.])
        np.testing.assert_allclose(r['water']+r['bed'], r['external_source']-r['irreversible_loss'])
        p['carrying_capacity_count_m3']=0
        with self.assertRaises(ValueError): self.rhs(p)

    def test_config_and_inventory_fail_closed(self):
        for p in ({'dark_enabled':True}, {'attachment_s':-1}, {'uv_coefficient_m2_j':float('nan')},
                  {'particle_associated_fraction':2.}, {'q10':2.}, {'fake_rate':1.}, {'dark_enabled':'yes'}):
            with self.subTest(p=p), self.assertRaises(ValueError): validate_parameters(p)
        with self.assertRaises(ValueError): self.rhs(water=[-1,2])
        with self.assertRaises(ValueError):
            reaction_tendencies([1],[0],[0],[1],{}, {})
        with self.assertRaises(ValueError):
            self.rhs({'uv_enabled':True,'uv_coefficient_m2_j':1.})

    def test_attenuation_and_full_shielding(self):
        p=dict(solar_enabled=True, solar_coefficient_m2_j=1., light_attenuation_m=1., solar_shielded_fraction=0.)
        r=self.rhs(p, {'solar_irradiance_w_m2':1., 'depth_m':2.})
        np.testing.assert_allclose(r['solar_water_loss'], np.array([100.,200.])*(1-np.exp(-2))/2)
        p['solar_shielded_fraction']=1.
        np.testing.assert_array_equal(self.rhs(p, {'solar_irradiance_w_m2':1.,'depth_m':2.})['solar_water_loss'], 0.)

if __name__ == '__main__': unittest.main()
