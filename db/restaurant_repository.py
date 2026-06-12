"""Read-only access to restaurants + branches for discovery."""
from sqlalchemy import select

from db.schema import restaurants_table as R, restaurant_branches_table as B
from db._util import to_float

class RestaurantRepository:
    # Searches restaurants and groups their branches.
    def __init__(self, engine):
        # Input: engine (SQLAlchemy engine).
        self._engine = engine

    def search(self, query: str = None, city: str = None,
               only_active: bool = True, limit: int = 20) -> list:
        # Inputs: query (brand/description ilike), city (branch city ilike),
        # only_active (keep active/unknown branches), limit (max rows, default 20).
        # Returns restaurants, each with a nested branches list.
        stmt = select(
            R.c.Id,
            R.c.BrandName,
            R.c.Description,
            R.c.Type,
            R.c.Status,
            B.c.Id.label("branch_id"),
            B.c.Name.label("branch_name"),
            B.c.Area,
            B.c.City,
            B.c.PhoneNumber,
            B.c.Latitude,
            B.c.Longitude,
            B.c.IsActive,
        ).select_from(R.join(B, B.c.RestaurantId == R.c.Id, isouter=True))
        if query:
            like = f"%{query}%"
            stmt = stmt.where(R.c.BrandName.ilike(like) | R.c.Description.ilike(like))
        if city:
            stmt = stmt.where(B.c.City.ilike(f"%{city}%"))
        if only_active:
            stmt = stmt.where((B.c.IsActive.is_(True)) | (B.c.IsActive.is_(None)))
        stmt = stmt.limit(limit)

        grouped: dict = {}
        with self._engine.connect() as conn:
            for r in conn.execute(stmt):
                rid = str(r.Id)
                entry = grouped.setdefault(
                    rid,
                    {
                        "restaurant_id": rid,
                        "name": r.BrandName,
                        "description": r.Description or "",
                        "type": r.Type,
                        "branches": [],
                    },
                )
                if r.branch_id:
                    entry["branches"].append(
                        {
                            "branch_id": str(r.branch_id),
                            "name": r.branch_name,
                            "area": r.Area,
                            "city": r.City,
                            "phone": r.PhoneNumber,
                            "lat": to_float(r.Latitude, None),
                            "lng": to_float(r.Longitude, None),
                        }
                    )
        return list(grouped.values())
