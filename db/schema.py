"""SQLAlchemy Core table definitions mapped to the REAL application schema.

Notion: this replaces the original mock schema. Nutrition is denormalized onto
`menus.MealSizes`; descriptive fields live on `menus.MenuMeals`.

All tables are used read-only.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID

menus_meta = MetaData(schema="menus")
food_meta = MetaData(schema="Food")
customers_meta = MetaData(schema="customers")
restaurants_meta = MetaData(schema="restaurants")

_UUID = UUID(as_uuid=False)

# --- menus schema -----------------------------------------------------------
meal_sizes_table = Table(
    "MealSizes",
    menus_meta,
    Column("Id", _UUID, primary_key=True),
    Column("Name", String),
    Column("SortOrder", Integer),
    Column("MealId", _UUID),  # -> menus.MenuMeals.Id
    Column("Calories", Numeric),
    Column("SodiumMg", Numeric),
    Column("SugarGrams", Numeric),
    Column("CalciumMg", Numeric),
    Column("Cholesterol", Numeric),
    Column("DietaryFiber", Numeric),
    Column("IronMg", Numeric),
    Column("PotassiumMg", Numeric),
    Column("Protein", Numeric),
    Column("SaturatedFat", Numeric),
    Column("TotalCarbohydrate", Numeric),
    Column("TotalFat", Numeric),
    Column("TransFat", Numeric),
    Column("VitaminAMcg", Numeric),
    Column("VitaminCMg", Numeric),
    Column("VitaminD", Numeric),
    Column("price_amount", Numeric),
    Column("price_currency", String),
    Column("Tags", Text),
)

menu_meals_table = Table(
    "MenuMeals",
    menus_meta,
    Column("Id", _UUID, primary_key=True),
    Column("CategoryId", _UUID),
    Column("Name", String),
    Column("Description", String),
    Column("Image", String),
    Column("Available", Boolean),
    Column("RestaurantId", _UUID),
    Column("Reviewed", Boolean),
)

menu_categories_table = Table(
    "MenuCategories",
    menus_meta,
    Column("Id", _UUID, primary_key=True),
    Column("RestaurantId", _UUID),
    Column("Name", String),
)

meal_ingredient_table = Table(
    "MealIngredient",
    menus_meta,
    Column("MealId", _UUID, primary_key=True),  # -> menus.MenuMeals.Id
    Column("FoodId", _UUID, primary_key=True),  # -> Food.Foods.Id
    Column("Name", Text),
)

ingredient_quantities_table = Table(
    "IngredientQuantities",
    menus_meta,
    Column("MealSizeId", _UUID, primary_key=True),  # -> menus.MealSizes.Id
    Column("MealIngredientId", _UUID, primary_key=True),  # == Food.Foods.Id
    Column("Quantity", Numeric),
)

# --- Food schema ------------------------------------------------------------
foods_table = Table(
    "Foods",
    food_meta,
    Column("Id", _UUID, primary_key=True),
    Column("Name", String),
    Column("Source", String),
    Column("ExternalId", String),
    Column("Calories", Numeric),
    Column("Protein", Numeric),
    Column("TotalCarbohydrate", Numeric),
    Column("TotalFat", Numeric),
    Column("SaturatedFat", Numeric),
    Column("TransFat", Numeric),
    Column("DietaryFiber", Numeric),
    Column("SugarGrams", Numeric),
    Column("SodiumMg", Numeric),
    Column("Cholesterol", Numeric),
    Column("CalciumMg", Numeric),
    Column("IronMg", Numeric),
    Column("PotassiumMg", Numeric),
    Column("VitaminAMcg", Numeric),
    Column("VitaminCMg", Numeric),
    Column("VitaminD", Numeric),
)

allergens_table = Table(
    "Allergens",
    food_meta,
    Column("Id", _UUID, primary_key=True),
    Column("Name", Text),
)

food_preferences_table = Table(
    "FoodPreferences",
    food_meta,
    Column("Id", _UUID, primary_key=True),
    Column("Name", Text),
)

# --- customers schema -------------------------------------------------------
customers_table = Table(
    "Customers",
    customers_meta,
    Column("Id", _UUID, primary_key=True),
    Column("Gender", Text),
    Column("Bday", Date),
    Column("Height", Integer),
    Column("Weight", Numeric),
    Column("ActivityRate", Text),
    Column("allergen_ids", ARRAY(_UUID)),
    Column("diet_preference_ids", ARRAY(_UUID)),
)

# --- restaurants schema -----------------------------------------------------
restaurants_table = Table(
    "Restaurants",
    restaurants_meta,
    Column("Id", _UUID, primary_key=True),
    Column("BrandName", String),
    Column("Description", String),
    Column("Type", Text),
    Column("Status", Text),
    Column("Logo", String),
    Column("Banner", String),
)

restaurant_branches_table = Table(
    "RestaurantBranches",
    restaurants_meta,
    Column("Id", _UUID, primary_key=True),
    Column("RestaurantId", _UUID),
    Column("Name", Text),
    Column("IsActive", Boolean),
    Column("Area", Text),
    Column("City", Text),
    Column("StreetName", Text),
    Column("StreetNumber", Text),
    Column("PhoneNumber", Text),
    Column("Latitude", Numeric),
    Column("Longitude", Numeric),
)
