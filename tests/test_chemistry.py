"""Physical sign, conservation and configuration checks for chemical reactions."""
import unittest

import numpy as np

from transport import chemistry


class ChemicalReactions(unittest.TestCase):
    def rate(self, parameters=None, environment=None, water=(1000.0, 500.0),
             bed=(0.0, 200.0), volume=(10.0, 20.0), area=(5.0, 8.0)):
        return chemistry.reaction_tendencies(water, bed, volume, area,
                                             parameters, environment)

    def test_disabled_reference_has_no_change(self):
        result = self.rate()
        for value in result.values():
            np.testing.assert_array_equal(value, [0.0, 0.0])

    def test_independent_rate_signs_and_ledger(self):
        p = {"biodegradation_enabled": True, "biodegradation_rate_s": 0.01,
             "hydrolysis_enabled": True, "hydrolysis_rate_s": 0.02,
             "bed_degradation_enabled": True, "bed_degradation_rate_s": 0.03,
             "photolysis_enabled": True, "photolysis_rate_s": 0.04}
        r = self.rate(p, {"light_reference": "natural_sunlight", "irradiance_ratio": [0, 0.5]})
        np.testing.assert_allclose(r["water"], [-30, -25])
        np.testing.assert_allclose(r["bed"], [0, -6])
        np.testing.assert_allclose(r["water"] + r["bed"], -r["irreversible_loss"])

    def test_exchange_adsorbs_and_desorbs_conservatively(self):
        p = {"sorption_enabled": True, "kd_l_kg": 1000,
             "exchange_rate_s": 0.01, "bed_dry_mass_kg_m2": 1}
        r = self.rate(p)
        # C=[100,25]; S=[5,8]; target=[500,200]; current bed=[0,200].
        np.testing.assert_allclose(r["bed"], [5, 0])
        np.testing.assert_allclose(r["water"] + r["bed"], 0)
        r = self.rate(p, water=[0, 0])
        np.testing.assert_allclose(r["bed"], [0, -2])
        np.testing.assert_allclose(r["water"], [0, 2])

    def test_koc_and_kd_are_alternative_paths(self):
        p = {"sorption_enabled": True, "kd_l_kg": 10,
             "koc_l_kg_oc": 1000, "organic_carbon_fraction": 0.01,
             "exchange_rate_s": 0.1, "bed_dry_mass_kg_m2": 2}
        kd = self.rate(p)
        p["partition_mode"] = "koc_foc"
        koc = self.rate(p)
        np.testing.assert_allclose(kd["sorption_to_bed"], koc["sorption_to_bed"])
        np.testing.assert_allclose(koc["water"] + koc["bed"], 0)

    def test_atmospheric_uptake_export_and_full_ledger(self):
        p = {"volatilization_enabled": True, "mass_transfer_velocity_m_s": 0.1,
             "equilibrium_water_concentration_mg_m3": 50,
             "bed_degradation_enabled": True, "bed_degradation_rate_s": 0.02}
        r = self.rate(p, {"water_surface_area_m2": [2, 4]})
        np.testing.assert_allclose(r["volatilization_net_export"], [10, -10])
        np.testing.assert_allclose(r["atmospheric_export"], [10, 0])
        np.testing.assert_allclose(r["atmospheric_input"], [0, 10])
        np.testing.assert_allclose(r["water"] + r["bed"],
                                   r["atmospheric_input"] - r["irreversible_loss"])

    def test_temperature_correction_is_explicit(self):
        p = {"biodegradation_enabled": True, "biodegradation_rate_s": 0.01,
             "biodegradation_theta": 2 ** 0.1}
        r = self.rate(p, {"temperature_c": [20, 30]})
        np.testing.assert_allclose(r["biodegradation"], [10, 10])
        with self.assertRaisesRegex(ValueError, "temperature_c"):
            self.rate(p)

    def test_rejects_enabled_missing_coefficients(self):
        for process, field in (("biodegradation", "biodegradation_rate_s"),
                               ("hydrolysis", "hydrolysis_rate_s"),
                               ("bed_degradation", "bed_degradation_rate_s"),
                               ("volatilization", "mass_transfer_velocity_m_s"),
                               ("sorption", "exchange_rate_s")):
            with self.subTest(process=process), self.assertRaisesRegex(ValueError, field):
                self.rate({process + "_enabled": True})

    def test_light_source_mismatch_and_missing_ratio(self):
        p = {"photolysis_enabled": True, "photolysis_rate_s": 0.1}
        with self.assertRaisesRegex(ValueError, "light_reference"):
            self.rate(p, {"light_reference": "artificial_irradiation", "irradiance_ratio": 1})
        with self.assertRaisesRegex(ValueError, "irradiance_ratio"):
            self.rate(p, {"light_reference": "natural_sunlight"})

    def test_rejects_nonphysical_or_misspelled_parameters(self):
        for p, message in [({"hydrolysis_rate_s": -1}, "hydrolysis_rate_s"),
                           ({"organic_carbon_fraction": 1.01}, "organic_carbon_fraction"),
                           ({"biodegradation_enabled": "false"}, "boolean"),
                           ({"biodegradation_theta": 0}, "biodegradation_theta"),
                           ({"partition_mode": "both"}, "partition_mode"),
                           ({"exchange_rate_s": float("nan")}, "finite"),
                           ({"hydrolisis_rate_s": 1}, "Unknown")]:
            with self.subTest(p=p), self.assertRaisesRegex(ValueError, message):
                self.rate(p)
        with self.assertRaisesRegex(ValueError, "water_volume_m3"):
            self.rate(volume=[0, 1])
        with self.assertRaisesRegex(ValueError, "water_mass"):
            self.rate(water=[-1, 0])
        with self.assertRaisesRegex(ValueError, "bed_area_m2"):
            self.rate(area=[float("inf"), 1])

    def test_array_parameters_scalar_state_broadcast(self):
        r = self.rate({"hydrolysis_enabled": True, "hydrolysis_rate_s": [0.1, 0.2]},
                      water=100, bed=0, volume=[1, 2], area=1)
        np.testing.assert_allclose(r["water"], [-10, -20])

    def test_input_state_is_not_modified(self):
        water = np.array([1000., 500.])
        bed = np.array([0., 200.])
        self.rate({"hydrolysis_enabled": True, "hydrolysis_rate_s": 0.1}, water=water, bed=bed)
        np.testing.assert_array_equal(water, [1000, 500])
        np.testing.assert_array_equal(bed, [0, 200])

    def test_defaults_presets_and_definitions_are_independent(self):
        atrazine = chemistry.load_preset("atrazine")
        self.assertEqual(atrazine["parameters"]["koc_l_kg_oc"], 122)
        self.assertIsNone(atrazine["parameters"]["hydrolysis_rate_s"])
        self.assertFalse(atrazine["parameters"]["sorption_enabled"])
        atrazine["parameters"]["hydrolysis_rate_s"] = 42
        self.assertIsNone(chemistry.load_preset("atrazine")["parameters"]["hydrolysis_rate_s"])
        self.assertEqual(set(chemistry.parameter_definitions()), set(chemistry.default_parameters()))
        with self.assertRaisesRegex(ValueError, "Unknown chemical preset"):
            chemistry.load_preset("missing")


if __name__ == "__main__":
    unittest.main()
