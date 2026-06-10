"""Recommendation orchestrator: load catalog -> targets -> filter -> rank."""
from dataclasses import dataclass, asdict

from models import UserProfile, ScoredMeal
from nutrition import compute_targets, NutritionTargets
from filters import filter_meals
from scorer import rank_meals


@dataclass
class RecommendationResult:
    # Output bundle: targets, counts before/after filtering, and ranked meals.
    user_targets: NutritionTargets
    meals_considered: int
    meals_after_filter: int
    ranked_meals: list[ScoredMeal]

    def to_dict(self) -> dict:
        # Serialize the result (and nested dataclasses) to plain dicts.
        return {
            "user_targets": asdict(self.user_targets),
            "meals_considered": self.meals_considered,
            "meals_after_filter": self.meals_after_filter,
            "ranked_meals": [asdict(m) for m in self.ranked_meals],
        }


class MealRecommender:
    # Ties the catalog repository to the nutrition/filter/scorer pipeline.
    def __init__(self, engine, meals_per_day: int = 3):
        # Inputs: engine (SQLAlchemy engine), meals_per_day (target split).
        from db.meal_repository import MealRepository

        self._repo = MealRepository(engine)
        self.meals_per_day = meals_per_day

    def recommend(self, profile: UserProfile, top_n: int = 10) -> RecommendationResult:
        # Inputs: profile (UserProfile), top_n (max meals to return).
        all_meals = self._repo.get_all(only_available=True, with_allergens=True)
        targets = compute_targets(profile, self.meals_per_day)
        filtered = filter_meals(all_meals, profile)
        ranked = rank_meals(filtered, profile, targets, top_n=top_n)
        return RecommendationResult(
            user_targets=targets,
            meals_considered=len(all_meals),
            meals_after_filter=len(filtered),
            ranked_meals=ranked,
        )
