from sqlalchemy import Table, Column, MetaData, Integer, Float, String, Text, ARRAY

meals_metadata = MetaData(schema="menus")

# Mirrors the MealSizes table in the menus schema.
meal_sizes_table = Table(
    "MealSizes",
    meals_metadata,
    Column("MealId",            Integer, primary_key=True),
    Column("Name",              String,  nullable=False),
    Column("Calories",          Float,   nullable=False, default=0.0),
    Column("SodiumMg",          Float,   nullable=True,  default=0.0),
    Column("SugarGrams",        Float,   nullable=True,  default=0.0),
    Column("CalciumMg",         Float,   nullable=True,  default=0.0),
    Column("Cholesterol",       Float,   nullable=True,  default=0.0),
    Column("DietaryFiber",      Float,   nullable=True,  default=0.0),
    Column("IronMg",            Float,   nullable=True,  default=0.0),
    Column("PotassiumMg",       Float,   nullable=True,  default=0.0),
    Column("Protein",           Float,   nullable=True,  default=0.0),
    Column("SaturatedFat",      Float,   nullable=True,  default=0.0),
    Column("TotalCarbohydrate", Float,   nullable=True,  default=0.0),
    Column("TotalFat",          Float,   nullable=True,  default=0.0),
    Column("TransFat",          Float,   nullable=True,  default=0.0),
    Column("VitaminAMcg",       Float,   nullable=True,  default=0.0),
    Column("VitaminCMg",        Float,   nullable=True,  default=0.0),
    Column("VitaminD",          Float,   nullable=True,  default=0.0),
    Column("Tags",              ARRAY(Text), nullable=True, default=[]),
)
