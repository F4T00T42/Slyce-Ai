"""Tool: generate a multi-day meal plan from the app catalog.

Builds on the recommender's ranking. For each day it fills meals_per_day slots
with distinct, allergen-safe, diet-compatible meals closest to the per-meal
calorie/protein targets, rotating the ranked pool to vary meals across days.
"""
from ai.tools._profile import get_profile, need_profile_response, PROFILE_ARG_SCHEMA
from nutrition import compute_targets
from filters import filter_meals
from scorer import rank_meals

SCHEMA = {
    "type": "function",
    "function": {
        "name": "meal_planner",
        "description": (
            "Generate a structured multi-day meal plan from the app catalog, "
            "respecting the user's calorie/protein targets, diet and allergies. "
            "Use for 'make me a meal plan', 'plan my week', 'diet plan'. "
            "DEFAULT PATH: pass `user_id` and the system loads that user's "
            "stored, already-translated profile — do NOT ask for stats they've "
            "already saved. Only pass `profile` to OVERRIDE when the user "
            "explicitly states different stats (e.g. for a friend)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Preferred input. The system loads this "
                    "user's stored, translated profile; no manual stats needed.",
                },
                "days": {"type": "integer", "default": 3, "minimum": 1, "maximum": 14},
                "meals_per_day": {"type": "integer", "default": 3, "minimum": 1, "maximum": 6},
                "profile": PROFILE_ARG_SCHEMA,
            },
        },
    },
}


def run(args: dict, ctx) -> dict:
    # Inputs: args (user_id?, days?=3, meals_per_day?=3, profile?), ctx (ToolContext).
    profile, missing = get_profile(args, ctx)
    if profile is None:
        return need_profile_response(missing)

    days = max(1, min(int(args.get("days", 3)), 14))
    meals_per_day = max(1, min(int(args.get("meals_per_day", 3)), 6))

    targets = compute_targets(profile, meals_per_day)
    all_meals = ctx.meal_repo.get_all(only_available=True, with_allergens=True)
    eligible = filter_meals(all_meals, profile)
    if not eligible:
        return {
            "status": "no_meals",
            "message": "No catalog meals match the diet/allergen constraints.",
            "targets": _targets_dict(targets),
        }

    ranked = rank_meals(eligible, profile, targets, top_n=len(eligible))
    by_id = {m.meal_id: m for m in eligible}
    pool = [r for r in ranked]

    plan = []
    cursor = 0
    needed = days * meals_per_day
    # Rotate through the ranked pool so days don't all repeat the top meal.
    rotation = [pool[i % len(pool)] for i in range(max(needed, len(pool)))]
    for d in range(days):
        day_meals = []
        seen = set()
        while len(day_meals) < meals_per_day and cursor < len(rotation) + len(pool):
            scored = rotation[cursor % len(rotation)]
            cursor += 1
            if scored.meal_id in seen:
                continue
            seen.add(scored.meal_id)
            meal = by_id[scored.meal_id]
            day_meals.append(
                {
                    "meal_id": meal.meal_id,
                    "name": meal.name,
                    "calories": round(meal.calories, 1),
                    "protein_g": round(meal.protein, 1),
                    "price": meal.price,
                    "currency": meal.currency,
                    "match_score": scored.score,
                }
            )
        plan.append(
            {
                "day": d + 1,
                "meals": day_meals,
                "day_calories": round(sum(m["calories"] for m in day_meals), 1),
                "day_protein_g": round(sum(m["protein_g"] for m in day_meals), 1),
            }
        )

    return {
        "status": "ok",
        "targets": _targets_dict(targets),
        "days": days,
        "meals_per_day": meals_per_day,
        "plan": plan,
    }


def _targets_dict(t) -> dict:
    # Input: t (NutritionTargets). Returns the daily/per-meal targets as a dict.
    return {
        "daily_calories": t.daily_calories,
        "meal_calories": t.meal_calories,
        "daily_protein_g": t.daily_protein_g,
        "meal_protein_g": t.meal_protein_g,
    }
