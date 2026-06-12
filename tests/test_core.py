"""Offline unit tests for the pure (dependency-free) core modules.

These cover the nutrition math, scorer, diet/allergen filters, the new
`allergy_conflicts` helper (M2), and the `db._util.to_float` helper (m6).
They only import modules that do not require external services (no FastAPI,
SQLAlchemy, Groq, Qdrant, sentence-transformers or Tavily), so they run in a
plain Python environment with just `pydantic` installed.

Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

# Make the project root importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import UserProfile, Meal
from nutrition import (
    compute_bmr,
    compute_targets,
    macro_calorie_fractions,
    NutritionTargets,
)
from scorer import rank_meals
from filters import (
    passes_allergen_check,
    passes_keto,
    filter_meals,
    allergy_conflicts,
)
from db._util import to_float


def make_profile(**overrides):
    base = dict(
        weight=80, height=180, age=30, gender="male",
        activity_level="moderately_active", goal="maintenance",
        diet="balanced", allergies=[],
    )
    base.update(overrides)
    return UserProfile(**base)


class TestNutrition(unittest.TestCase):
    def test_bmr_mifflin_male_and_female(self):
        # Mifflin-St Jeor: 10*w + 6.25*h - 5*age (+5 male / -161 female).
        self.assertAlmostEqual(compute_bmr(make_profile()), 1780.0)
        self.assertAlmostEqual(compute_bmr(make_profile(gender="female")), 1614.0)

    def test_goal_adjustment_applied(self):
        maint = compute_targets(make_profile(goal="maintenance"))
        loss = compute_targets(make_profile(goal="fat_loss"))
        gain = compute_targets(make_profile(goal="muscle_gain"))
        self.assertLess(loss.daily_calories, maint.daily_calories)
        self.assertGreater(gain.daily_calories, maint.daily_calories)

    def test_meal_split(self):
        t = compute_targets(make_profile(), meals_per_day=4)
        self.assertEqual(t.meals_per_day, 4)
        self.assertAlmostEqual(t.meal_calories, round(t.daily_calories / 4, 1))

    def test_summary_is_dict_with_all_fields(self):
        t = compute_targets(make_profile())
        s = t.summary()
        self.assertIsInstance(s, dict)
        for key in (
            "daily_calories", "meal_calories", "daily_protein_g",
            "meal_protein_g", "bmr", "tdee", "meals_per_day",
        ):
            self.assertIn(key, s)

    def test_macro_fractions_zero_calories(self):
        m = Meal(meal_id="1", name="empty", calories=0)
        self.assertEqual(
            macro_calorie_fractions(m), {"carb": 0.0, "protein": 0.0, "fat": 0.0}
        )

    def test_macro_fractions_values(self):
        # 400 kcal: 50g carb (200), 25g protein (100), ~11.11g fat (100).
        m = Meal(
            meal_id="1", name="meal", calories=400,
            total_carbohydrate=50, protein=25, total_fat=100 / 9,
        )
        frac = macro_calorie_fractions(m)
        self.assertAlmostEqual(frac["carb"], 0.5)
        self.assertAlmostEqual(frac["protein"], 0.25)
        self.assertAlmostEqual(frac["fat"], 0.25)


class TestFiltersDiet(unittest.TestCase):
    def test_passes_keto_true_and_false(self):
        keto_meal = Meal(
            meal_id="1", name="keto", calories=400,
            total_carbohydrate=2, protein=20, total_fat=33,
        )  # carb ~0.02, fat ~0.74
        carby_meal = Meal(
            meal_id="2", name="carby", calories=400,
            total_carbohydrate=60, protein=20, total_fat=5,
        )
        self.assertTrue(passes_keto(keto_meal))
        self.assertFalse(passes_keto(carby_meal))

    def test_filter_meals_drops_allergen(self):
        safe = Meal(meal_id="1", name="safe", calories=400, tags=[])
        unsafe = Meal(meal_id="2", name="nutty", calories=400, tags=["Tree Nuts"])
        profile = make_profile(allergies=["Tree Nuts"], diet="balanced")
        kept = filter_meals([safe, unsafe], profile, apply_diet=False)
        ids = {m.meal_id for m in kept}
        self.assertIn("1", ids)
        self.assertNotIn("2", ids)

    def test_passes_allergen_check(self):
        meal = Meal(meal_id="1", name="m", calories=400, tags=["Milk"])
        self.assertFalse(passes_allergen_check(meal, ["milk"]))
        self.assertTrue(passes_allergen_check(meal, ["Peanuts"]))
        self.assertTrue(passes_allergen_check(meal, []))


class TestAllergyConflicts(unittest.TestCase):
    def test_synonym_dairy_matches_milk(self):
        self.assertEqual(allergy_conflicts(["dairy"], ["Milk"]), ["Milk"])

    def test_synonym_nuts_matches_tree_nuts(self):
        self.assertEqual(allergy_conflicts(["nuts"], ["Tree Nuts"]), ["Tree Nuts"])

    def test_fish_not_matching_shellfish(self):
        self.assertEqual(allergy_conflicts(["fish"], ["Shellfish"]), [])
        self.assertEqual(allergy_conflicts(["shellfish"], ["Fish"]), [])

    def test_peanut_matches(self):
        self.assertEqual(allergy_conflicts(["peanuts"], ["Peanut"]), ["Peanut"])

    def test_no_user_allergies_or_no_detected(self):
        self.assertEqual(allergy_conflicts([], ["Milk"]), [])
        self.assertEqual(allergy_conflicts(["Milk"], []), [])

    def test_dedup_and_order_preserved(self):
        out = allergy_conflicts(["dairy", "gluten"], ["Wheat", "Milk", "Milk"])
        self.assertEqual(out, ["Wheat", "Milk"])


class TestScorer(unittest.TestCase):
    def test_rank_orders_by_fit(self):
        profile = make_profile(goal="maintenance")
        targets = compute_targets(profile)
        on_target = Meal(
            meal_id="good", name="on target",
            calories=targets.meal_calories,
            protein=targets.meal_protein_g,
            total_carbohydrate=40, total_fat=15,
        )
        way_off = Meal(
            meal_id="bad", name="way off",
            calories=targets.meal_calories * 3,
            protein=0, total_carbohydrate=200, total_fat=80,
        )
        ranked = rank_meals([way_off, on_target], profile, targets, top_n=2)
        self.assertEqual(ranked[0].meal_id, "good")
        self.assertGreaterEqual(ranked[0].score, ranked[1].score)


class TestToFloat(unittest.TestCase):
    def test_none_returns_default(self):
        self.assertIsNone(to_float(None, None))
        self.assertEqual(to_float(None, 0.0), 0.0)

    def test_numeric_and_string(self):
        self.assertEqual(to_float(5, None), 5.0)
        self.assertEqual(to_float("3.5", None), 3.5)

    def test_invalid_returns_default(self):
        self.assertIsNone(to_float("abc", None))


if __name__ == "__main__":
    unittest.main()
