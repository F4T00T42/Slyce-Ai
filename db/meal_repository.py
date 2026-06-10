"""Read-only access to orderable meals (menus.MealSizes joined to MenuMeals).

Each returned `Meal` is a meal *size* (the unit the app orders by), enriched
with the parent meal's name/description/restaurant and, optionally, detected
allergen tags from its ingredients.
"""
from sqlalchemy import select

from models import Meal
from db.schema import meal_sizes_table as MS, menu_meals_table as MM
from db.ingredient_repository import IngredientRepository


def _f(v) -> float:
    return float(v) if v is not None else 0.0


class MealRepository:
    def __init__(self, engine):
        self._engine = engine
        self._ingredients = IngredientRepository(engine)

    def _base_select(self):
        return select(
            MS.c.Id,
            MS.c.Name.label("size_name"),
            MS.c.MealId,
            MS.c.Calories,
            MS.c.SodiumMg,
            MS.c.SugarGrams,
            MS.c.CalciumMg,
            MS.c.Cholesterol,
            MS.c.DietaryFiber,
            MS.c.IronMg,
            MS.c.PotassiumMg,
            MS.c.Protein,
            MS.c.SaturatedFat,
            MS.c.TotalCarbohydrate,
            MS.c.TotalFat,
            MS.c.TransFat,
            MS.c.VitaminAMcg,
            MS.c.VitaminCMg,
            MS.c.VitaminD,
            MS.c.price_amount,
            MS.c.price_currency,
            MS.c.Tags,
            MM.c.Name.label("meal_name"),
            MM.c.Description,
            MM.c.Available,
            MM.c.RestaurantId,
        ).select_from(MS.join(MM, MS.c.MealId == MM.c.Id))

    def _map(self, row) -> Meal:
        tags = []
        if row.Tags:
            tags = [t.strip() for t in str(row.Tags).replace(";", ",").split(",") if t.strip()]
        meal_name = row.meal_name or ""
        size = row.size_name or ""
        display = f"{meal_name} ({size})" if size else meal_name
        return Meal(
            meal_id=str(row.Id),
            name=display,
            calories=_f(row.Calories),
            sodium_mg=_f(row.SodiumMg),
            sugar_grams=_f(row.SugarGrams),
            calcium_mg=_f(row.CalciumMg),
            cholesterol=_f(row.Cholesterol),
            dietary_fiber=_f(row.DietaryFiber),
            iron_mg=_f(row.IronMg),
            potassium_mg=_f(row.PotassiumMg),
            protein=_f(row.Protein),
            saturated_fat=_f(row.SaturatedFat),
            total_carbohydrate=_f(row.TotalCarbohydrate),
            total_fat=_f(row.TotalFat),
            trans_fat=_f(row.TransFat),
            vitamin_a_mcg=_f(row.VitaminAMcg),
            vitamin_c_mg=_f(row.VitaminCMg),
            vitamin_d=_f(row.VitaminD),
            tags=tags,
            menu_meal_id=str(row.MealId),
            size_name=size,
            description=row.Description or "",
            price=_f(row.price_amount),
            currency=row.price_currency or "",
            restaurant_id=str(row.RestaurantId) if row.RestaurantId else "",
            available=bool(row.Available),
        )

    def _attach_allergens(self, meals: list) -> None:
        menu_ids = list({m.menu_meal_id for m in meals if m.menu_meal_id})
        names_by_meal = self._ingredients.ingredient_names_for_meals(menu_ids)
        for m in meals:
            names = names_by_meal.get(m.menu_meal_id, [])
            m.ingredients = names
            detected = IngredientRepository.detect_allergens(names)
            # Merge detected allergens into tags (used by the allergen filter).
            merged = {t for t in m.tags}
            merged.update(detected)
            m.tags = sorted(merged)

    def get_all(self, only_available: bool = True, with_allergens: bool = True) -> list:
        stmt = self._base_select()
        if only_available:
            stmt = stmt.where(MM.c.Available.is_(True))
        with self._engine.connect() as conn:
            meals = [self._map(r) for r in conn.execute(stmt)]
        if with_allergens:
            self._attach_allergens(meals)
        return meals

    def get_by_ids(self, size_ids: list, with_allergens: bool = True) -> list:
        if not size_ids:
            return []
        stmt = self._base_select().where(MS.c.Id.in_(size_ids))
        with self._engine.connect() as conn:
            meals = [self._map(r) for r in conn.execute(stmt)]
        if with_allergens:
            self._attach_allergens(meals)
        return meals

    def search(self, query: str = None, max_calories: float = None,
               min_protein: float = None, limit: int = 20) -> list:
        stmt = self._base_select().where(MM.c.Available.is_(True))
        if query:
            like = f"%{query}%"
            stmt = stmt.where(MM.c.Name.ilike(like) | MM.c.Description.ilike(like))
        if max_calories is not None:
            stmt = stmt.where(MS.c.Calories <= max_calories)
        if min_protein is not None:
            stmt = stmt.where(MS.c.Protein >= min_protein)
        stmt = stmt.limit(limit)
        with self._engine.connect() as conn:
            meals = [self._map(r) for r in conn.execute(stmt)]
        self._attach_allergens(meals)
        return meals
