from dataclasses import dataclass, asdict

from models import UserProfile, Meal, ScoredMeal
from nutrition import compute_targets, NutritionTargets
from filters import filter_meals
from scorer import rank_meals


# Holds the result of one recommendation pass.
@dataclass
class RecommendationResult:
    user_targets: NutritionTargets
    meals_considered: int
    meals_after_filter: int
    ranked_meals: list[ScoredMeal]

    def to_dict(self) -> dict:
        return {
            "user_targets":       asdict(self.user_targets),
            "meals_considered":   self.meals_considered,
            "meals_after_filter": self.meals_after_filter,
            "ranked_meals":       [asdict(m) for m in self.ranked_meals],
        }


class MealRecommender:
    # Instantiated once at startup; recommend() is called per request.

    def __init__(self, engine, meals_per_day: int = 3):
        from db.meal_repository import MealRepository
        self._repo = MealRepository(engine)
        self.meals_per_day = meals_per_day

    def recommend(self, profile: UserProfile, top_n: int = 10) -> RecommendationResult:
        # Loads all meals, computes targets, applies filters, then ranks.
        all_meals = self._repo.get_all()
        targets   = compute_targets(profile, self.meals_per_day)
        filtered  = filter_meals(all_meals, profile)
        ranked    = rank_meals(filtered, profile, targets, top_n=top_n)

        return RecommendationResult(
            user_targets=targets,
            meals_considered=len(all_meals),
            meals_after_filter=len(filtered),
            ranked_meals=ranked,
        )
