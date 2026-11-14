import unittest

import numpy as np

from analysis import confirmatory as C
from analysis import power_sim as PS


class HolmTest(unittest.TestCase):
    def test_steps_down_and_stops_at_the_first_failure(self):
        # thresholds, smallest p first: 0.01, 0.0125, 0.0167, 0.025, 0.05
        self.assertEqual(C.holm_reject(np.array([[0.001, 0.04, 0.03, 0.02, 0.5]])).tolist(),
                         [[True, False, False, False, False]])
        self.assertEqual(C.holm_reject(np.array([[0.049, 0.001, 0.016, 0.024, 0.011]])).tolist(), [[True] * 5])
        self.assertEqual(C.holm_reject(np.array([[0.011, 0.5, 0.5, 0.5, 0.5]])).tolist(), [[False] * 5])

    def test_exact_bound_matches_section_8(self):
        self.assertAlmostEqual(C.exact_zero_bound(300), 0.00994, places=4)   # "about 1 percent at n = 300"


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(7)

    def test_no_differences_anywhere_is_no_evidence(self):
        d = np.zeros((3, 50, 2))
        self.assertTrue((C.boot_pvalues(d, C.boot_weights(self.rng, 199, 50)) == 1.0).all())

    def test_identical_nonzero_differences_give_the_smallest_p(self):
        d = np.ones((2, 40, 1))        # as efficacy was in the confirmation run: 100 points in every history
        p = C.boot_pvalues(d, C.boot_weights(self.rng, 199, 40))
        self.assertTrue(np.allclose(p, 1 / 200))

    def test_thirds_do_not_trip_the_degenerate_branches(self):
        d = np.full((1, 60, 1), 1 / 3)  # equal in every history, not exactly representable
        self.assertTrue(np.allclose(C.boot_pvalues(d, C.boot_weights(self.rng, 199, 60)), 1 / 200))

    def test_a_clear_effect_is_found_and_contrasts_are_tested_separately(self):
        d = np.stack([self.rng.normal(1.0, 1.0, (4, 100)), self.rng.normal(0.0, 1.0, (4, 100))], axis=2)
        p = C.boot_pvalues(d, C.boot_weights(self.rng, 499, 100))
        self.assertEqual(p.shape, (4, 2))
        self.assertTrue((p[:, 0] < 0.01).all())
        self.assertTrue((p[:, 1] > 0.01).all())

    def test_matmul_agrees_with_einsum(self):
        w = C.boot_weights(self.rng, 99, 300)
        x = self.rng.random((300, 50))
        with np.errstate(all="ignore"):
            product = w @ x
        self.assertTrue(np.isfinite(product).all())
        self.assertTrue(np.allclose(product, np.einsum("bn,nk->bk", w, x)))

    def test_rare_differences_stay_conservative(self):
        d = np.zeros((1, 100, 1))
        d[0, :2, 0] = 1.0              # two histories of a hundred differ
        self.assertGreater(C.boot_pvalues(d, C.boot_weights(self.rng, 499, 100))[0, 0], 0.05)

    def test_false_rejections_are_near_five_percent_under_the_null(self):
        d = self.rng.normal(0.0, 1.0, (800, 100, 1))
        rate = (C.boot_pvalues(d, C.boot_weights(self.rng, 399, 100)) <= 0.05).mean()
        self.assertTrue(0.02 < rate < 0.09, rate)


class ScenarioTest(unittest.TestCase):
    def test_configurations_carry_the_declared_effects(self):
        by = {}
        for sc in PS.scenarios():
            by.setdefault(sc["config"], sc)
        null = {c: 0.0 for c in C.CONTRASTS}
        self.assertEqual(PS.true_effects(by["one_strike"]), dict(null, agency_redundant=0.1))
        self.assertEqual(PS.true_effects(by["reward_only"]), dict(null, reward_agency=0.2))
        self.assertEqual(PS.true_effects(by["all_five"]),
                         {"efficacy": 0.1, "agency_redundant": 0.1, "agency_pivotal": 0.1, "cut_type": 0.1,
                          "reward_agency": 0.2})
        self.assertEqual(PS.true_effects(by["global_null"]), null)
        pilot = PS.true_effects(by["pilot_like"])
        self.assertEqual((pilot["agency_redundant"], pilot["agency_pivotal"], pilot["cut_type"],
                          pilot["reward_agency"]), (0.1, 0.1, 0.1, 0.2))

    def test_every_kind_of_history_variation_keeps_the_cell_averages(self):
        rng = np.random.default_rng(3)
        means = [0.0, 0.1, 0.45, 1.0]
        for het in PS.HETS:
            for link in PS.LINKS:
                p = PS.cell_probabilities(rng, means, [het] * 4, link, 4, 20000)
                self.assertTrue(np.allclose(p.mean(axis=(0, 1)), means, atol=0.01), (het, link, p.mean(axis=(0, 1))))
        whole = PS.cell_probabilities(rng, [0.3], ["all_or_nothing"], 0.0, 1, 500)
        self.assertTrue(set(np.unique(whole)) <= {0.0, 1.0})

    def test_linked_cells_give_a_steadier_difference(self):
        rng = np.random.default_rng(5)
        sd = {}
        for link in (0.0, 0.5):
            p = PS.cell_probabilities(rng, [0.4, 0.4], ["all_or_nothing"] * 2, link, 1, 40000)
            sd[link] = (p[0, :, 0] - p[0, :, 1]).std()
        self.assertLess(sd[0.5], sd[0.0])

    def test_simulation_is_reproducible_and_sees_easy_and_null_cases(self):
        scs = {(s["config"], s["base"], s["het_strike"], s["link"]): s for s in PS.scenarios()}
        easy = scs[("one_strike", 0.0, "homogeneous", 0.0)]
        a = PS.simulate(easy, 300, 60, 199, seed=1)
        self.assertEqual(a, PS.simulate(easy, 300, 60, 199, seed=1))
        self.assertGreater(a["power_holm"]["agency_redundant"], 0.9)
        self.assertLess(a["power_holm"]["efficacy"], 0.2)
        flat = PS.simulate(scs[("global_null", 0.45, "homogeneous", 0.0)], 300, 100, 199, seed=1)
        self.assertLess(flat["any_false_rejection"], 0.2)


if __name__ == "__main__":
    unittest.main()
