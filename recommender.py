"""Recommendation orchestrator: load catalog -> targets -> filter -> rank.

Diet is treated as a PREFERENCE, not a hard requirement: allergens are the only
hard gate (safety), while diet shapes ranking and is applied as a filter only
when enough diet-compatible meals remain. This guarantees the recommender — the
home page's main feature — always returns meals when the catalog is non-empty.
"""
from dataclasses import dataclass, asdict

from models import UserProfile, ScoredMeal
from nutrition import compute_targets, NutritionTargets
from filters import filter_meals
from scorer import rank_meals


@dataclass
class RecommendationResult:
    # Output bundle: targets, counts before/after filtering, ranked meals, and
    # whether the diet filter was enforced (plus a note when constraints relaxed).
    user_targets: NutritionTargets
    meals_considered: int
    meals_after_filter: int
    ranked_meals: list[ScoredMeal]
    diet_enforced: bool = True
    note: str | None = None

    def to_dict(self) -> dict:
        # Serialize the result (and nested dataclasses) to plain dicts.
        return {
            "user_targets": asdict(self.user_targets),
            "meals_considered": self.meals_considered,
            "meals_after_filter": self.meals_after_filter,
            "ranked_meals": [asdict(m) for m in self.ranked_meals],
            "diet_enforced": self.diet_enforced,
            "note": self.note,
        }


class MealRecommender:
    # Ties the catalog repository to the nutrition/filter/scorer pipeline.
    def __init__(self, engine, meals_per_day: int = 3):
        # Inputs: engine (SQLAlchemy engine), meals_per_day (target split).
        from db.meal_repository import MealRepository

        self._repo = MealRepository(engine)
        self.meals_per_day = meals_per_day

    def recommend(self, profile: UserProfile, top_n: int = 12) -> RecommendationResult:
        # Inputs: profile (UserProfile), top_n (max meals to return, default 12).
        # Always returns meals when the catalog is non-empty, via a fallback ladder:
        #   1) allergen-safe AND diet-compatible (if that yields >= top_n)
        #   2) allergen-safe only (diet relaxed; still boosts ranking)
        #   3) full available catalog (only if allergen filtering removed everything)
        all_meals = self._repo.get_all(only_available=True, with_allergens=True)
        targets = compute_targets(profile, self.meals_per_day)

        safe = filter_meals(all_meals, profile, apply_diet=False)
        diet_compatible = filter_meals(all_meals, profile, apply_diet=True)

        if len(diet_compatible) >= top_n:
            pool, diet_enforced, note = diet_compatible, True, None
        elif diet_compatible:
            pool, diet_enforced = safe, False
            note = (
                "Relaxed the diet filter to surface enough meals; "
                "diet still influences ranking."
            )
        elif safe:
            pool, diet_enforced = safe, False
            note = (
                "No meals matched the diet filter; showing allergen-safe meals "
                "ranked by overall fit."
            )
        else:
            # Last resort: never leave the home page empty.
            pool, diet_enforced = all_meals, False
            note = (
                "Could not satisfy all constraints; showing the available "
                "catalog ranked by fit."
            )

        ranked = rank_meals(pool, profile, targets, top_n=top_n)
        return RecommendationResult(
            user_targets=targets,
            meals_considered=len(all_meals),
            meals_after_filter=len(pool),
            ranked_meals=ranked,
            diet_enforced=diet_enforced,
            note=note,
        )
