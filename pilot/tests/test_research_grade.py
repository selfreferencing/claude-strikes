"""The research-grade study's analysis (analysis/research_grade.py): rules fixed before any data."""

import collections
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "analysis"))
import research_grade as G  # noqa: E402


def dataset(rates, histories=40, draws=2):
    """{situation: {history: [struck, decisions]}} with each history striking at the given rate."""
    data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for s, r in rates.items():
        for i in range(histories):
            struck = round(r * draws) if i % 2 == 0 else min(draws, round(r * draws + (0.5 if r < 1 else 0)))
            data[s][f"h{i}"] = [struck, draws]
    return data


class RulesTest(unittest.TestCase):
    def test_the_decision_rule(self):
        self.assertEqual(G.rule([(0.02, (-0.05, 0.08)), (0.0, (-0.09, 0.09))]), "alike")
        self.assertEqual(G.rule([(0.20, (0.05, 0.35)), (0.0, (-0.05, 0.05))]), "unequal")
        self.assertEqual(G.rule([(0.12, (0.02, 0.22)), (0.0, (-0.05, 0.05))]), "not settled")   # under 15 points
        self.assertEqual(G.rule([(0.20, (-0.02, 0.40)), (0.0, (-0.05, 0.05))]), "not settled")  # interval crosses 0
        self.assertEqual(G.rule([(0.0, (-0.11, 0.05))]), "not settled")                          # outside 10 points
        self.assertEqual(G.rule([(0.0, None)]), "no data")
        # A missing comparison cannot be alike, but an observed one can still be unequal (Pro, 26 October).
        self.assertEqual(G.rule([(0.20, (0.05, 0.35)), (0.0, None)]), "unequal")
        self.assertEqual(G.rule([(0.0, (-0.05, 0.05)), (0.0, None)]), "not settled")

    def test_slope_and_sign_test(self):
        self.assertAlmostEqual(G.slope([(2, 1.0), (4, 0.5), (6, 0.0)]), -0.25)
        self.assertIsNone(G.slope([(2, 1.0)]))
        self.assertEqual(G.sign_p(0, 0), 1.0)
        self.assertAlmostEqual(G.sign_p(10, 0), 2 / 2 ** 10)

    def test_a_flat_history_is_a_tie(self):
        # Pro's example: shares 0, 1, 0, 0, 1/2 at fees 2 to 6 have slope exactly zero; floats gave 5.55e-18.
        data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
        for (s, _), (w, n) in zip(G.PRICE[:5], ((0, 2), (2, 2), (0, 2), (0, 2), (1, 2))):
            data[s]["h"] = [w, n]
        self.assertEqual(G.history_slopes(data, ["h"]), {"h": 0.0})

    def test_the_situations_are_the_preregistered_25(self):
        self.assertEqual(len(G.SITUATIONS), 25)
        self.assertEqual(len(set(G.SITUATIONS)), 25)
        self.assertEqual(G.SEED, 20261026)


class AnalysisTest(unittest.TestCase):
    def test_a_falling_price_curve_is_supported_and_equal_labels_are_alike(self):
        rates = {s: r for (s, _), r in zip(G.PRICE, (1.0, 1.0, 0.5, 0.5, 0.0, 0.0))}
        rates.update({"UD-p50": 0.5, "UD-p25": 0.0, "UD-p75": 1.0, "M0": 0.5, "LW-f0": 0.0, "M0-against": 1.0,
                      "M1-against": 0.5, "M1": 0.0, "J-team-ai": 0.0})
        rates.update({l: rates[c] for l, c in G.LOTTERY})
        rates.update({f"DPL-{k}-f{f}": rates[f"DP-f{f}"] for k in ("person", "ai", "same") for f in (4, 6)})
        data = dataset(rates)
        version = {f"h{i}": ("workplace-a", "neutral-c")[i % 2] for i in range(40)}
        text = "\n".join(G.analyse("Test model", data, version))
        self.assertIn("H1 price", text)
        self.assertRegex(text, r"H1 price[^\n]*SUPPORTED")
        self.assertNotRegex(text, r"H1 price[^\n]*NOT SUPPORTED")
        self.assertIn("H4 who was wronged, person against ai: EQUAL RATES UNDER THESE LABELS AT FEES 4 AND 6", text)
        self.assertIn("H2 cost and chance: EQUAL RATES AT THE TWO TESTED RATIOS", text)
        self.assertRegex(text, r"H3 strikers[^\n]*SUPPORTED")
        self.assertIn("Fee 4, AI agent against the same model", text)
        self.assertRegex(text, r"in credits [+-]\d")


    def test_a_sign_majority_against_the_mean_is_not_supported(self):
        # GPT Pro's example: 180 histories half a point up, 120 a whole point down. The sign test favours
        # the prediction; the mean goes the other way, so H3 is not supported.
        data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
        for i in range(300):
            h = f"h{i}"
            data["M0"][h], data["LW-f0"][h] = ([1, 2], [0, 2]) if i < 180 else ([0, 2], [2, 2])
        version = {f"h{i}": "workplace-a" for i in range(300)}
        text = "\n".join(G.analyse("Test model", data, version))
        self.assertRegex(text, r"H3 strikers[^\n]*predicted direction in 180 histories, reverse in 120")
        self.assertRegex(text, r"H3 strikers[^\n]*NOT SUPPORTED")

    def test_the_credits_conversion_has_no_finite_bound_when_price_does_not_bite(self):
        rates = {s: 0.5 for s in G.SITUATIONS}
        rates.update({l: 0.0 for l, _ in G.LOTTERY})
        data = dataset(rates)
        version = {f"h{i}": "workplace-a" for i in range(40)}
        text = "\n".join(G.analyse("Test model", data, version))
        self.assertIn("in credits: no finite bound", text)


class IntervalTest(unittest.TestCase):
    def test_resamples_keep_each_versions_count(self):
        version = {f"h{i}": ("workplace-a", "neutral-c")[i < 10] for i in range(40)}
        counts = []
        G.boot(lambda sample: counts.append(sum(version[h] == "neutral-c" for h in sample)) or 0, version, version)
        self.assertEqual(set(counts), {10})

    def test_a_collapsed_interval_takes_the_exact_bound(self):
        q = 1 - 0.05 ** (1 / 300)                       # Clopper-Pearson with none of 300 differing
        self.assertAlmostEqual(G.cp_upper(0, 300), q, places=9)
        data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
        for i in range(300):
            data["A"][f"h{i}"], data["B"][f"h{i}"] = [2, 2], [2, 2]
        version = {f"h{i}": "workplace-a" for i in range(300)}
        point, iv, n, _ = G.compare(data, version, ["A"], ["B"])
        self.assertEqual((point, n), (0.0, 300))
        self.assertAlmostEqual(iv[0], -q, places=9)
        self.assertAlmostEqual(iv[1], q, places=9)
        self.assertEqual(G.rule([(point, iv)]), "alike")

    def test_the_exact_bound_covers_a_mean_near_the_edge(self):
        # Pro's example: differences +1 with probability .995 and -1 with .005 (true mean .99). When all 300
        # observed are +1, the interval must still reach .99; the old floor stopped at .990064.
        data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
        for i in range(300):
            data["A"][f"h{i}"], data["B"][f"h{i}"] = [2, 2], [0, 2]
        version = {f"h{i}": "workplace-a" for i in range(300)}
        point, iv, _, _ = G.compare(data, version, ["A"], ["B"])
        self.assertEqual(point, 1.0)
        self.assertLess(iv[0], 0.99)

    def test_the_bound_holds_under_within_version_resampling(self):
        # Pro's third-round example: three versions always 0, three always 1 (true equal-weight mean .495 when
        # the latter are 1 with probability .99). Every within-version resample gives .5, so the bound must
        # come from each version's own reference value, not the pooled most common one.
        names = ("workplace-a", "workplace-b", "workplace-c", "neutral-a", "neutral-b", "neutral-c")
        data = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
        version = {}
        for v_i, name in enumerate(names):
            for i in range(50):
                h = f"{name}-{i}"
                version[h] = name
                data["A"][h], data["B"][h] = ([2, 2], [0, 2]) if v_i < 3 else ([2, 2], [2, 2])
        point, iv, n, _ = G.compare(data, version, ["A"], ["B"])
        self.assertEqual((point, n), (0.5, 300))
        self.assertLess(iv[0], 0.495)

    def test_the_bound_protects_a_collapsed_slope(self):
        # Pro's slope example: every history falls 0.4 per credit (shares 1, 1, 0, 0 at fees 3 to 6) while the
        # true mean fall is .3995; the bound must reach it.
        falls = {f"h{i}": 0.4 for i in range(300)}
        (lo, hi), k = G.sparse_bound(falls, {h: "workplace-a" for h in falls}, -1.0, 1.0)
        self.assertEqual(k, 0)
        self.assertLess(lo, 0.3995)

    def test_unequal_counts_either_direction(self):
        self.assertEqual(G.rule([(-0.20, (-0.35, -0.05))]), "unequal")


if __name__ == "__main__":
    unittest.main()
