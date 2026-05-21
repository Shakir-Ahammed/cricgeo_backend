"""
Venue service: create, fetch, and search venues.
"""

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.venues.model import Venue
from app.modules.venues.schema import VenueCreate, VenueSearchParams


async def create_venue(db: AsyncSession, user_id: int, data: VenueCreate) -> Venue:
    """INSERT a new venue with created_by = user_id."""
    venue = Venue(
        name=data.name,
        address=data.address,
        city_id=data.city_id,
        country_id=data.country_id,
        latitude=data.latitude,
        longitude=data.longitude,
        is_public=data.is_public,
        created_by=user_id,
    )
    db.add(venue)
    await db.commit()
    await db.refresh(venue)
    return venue


async def get_venue(db: AsyncSession, venue_id: int) -> Optional[Venue]:
    """SELECT a single active venue by primary key."""
    result = await db.execute(
        select(Venue).where(Venue.id == venue_id, Venue.status == "active")
    )
    return result.scalar_one_or_none()


async def search_venues(
    db: AsyncSession,
    params: VenueSearchParams,
    current_user_id: Optional[int] = None,
) -> dict:
    """
    Search venues with optional filters and Haversine proximity ordering.
    Privacy rule: private venues (is_public=False) are only visible to their creator.
    """
    stmt = select(Venue).where(Venue.status == "active")

    # Privacy filter — private venues only visible to their creator.
    # If no authenticated user, only public venues are shown.
    if current_user_id is not None:
        stmt = stmt.where(
            or_(Venue.is_public == True, Venue.created_by == current_user_id)  # noqa: E712
        )
    else:
        stmt = stmt.where(Venue.is_public == True)  # noqa: E712

    # Full-text search on name or address
    if params.q:
        pattern = f"%{params.q}%"
        stmt = stmt.where(
            or_(
                Venue.name.ilike(pattern),
                Venue.address.ilike(pattern),
            )
        )

    # City filter
    if params.city_id is not None:
        stmt = stmt.where(Venue.city_id == params.city_id)

    # Haversine distance filter + ordering (no PostGIS required)
    distance_col = None
    if params.lat is not None and params.lon is not None:
        lat = params.lat
        lon = params.lon

        # Haversine formula expressed entirely in SQL via SQLAlchemy func.*
        # distance (km) = 6371 * acos(
        #     cos(radians(user_lat)) * cos(radians(venue_lat))
        #     * cos(radians(venue_lon) - radians(user_lon))
        #     + sin(radians(user_lat)) * sin(radians(venue_lat))
        # )
        distance_col = (
            6371
            * func.acos(
                # Clamp to [-1, 1] to guard against floating-point rounding
                # that can push the dot product marginally outside acos's domain
                # (most common when the two points are at the same location).
                func.least(
                    1.0,
                    func.greatest(
                        -1.0,
                        func.cos(func.radians(lat))
                        * func.cos(func.radians(Venue.latitude))
                        * func.cos(func.radians(Venue.longitude) - func.radians(lon))
                        + func.sin(func.radians(lat))
                        * func.sin(func.radians(Venue.latitude)),
                    ),
                )
            )
        ).label("distance_km")

        # Venues without coordinates cannot be included in proximity results.
        stmt = stmt.where(
            Venue.latitude.is_not(None),
            Venue.longitude.is_not(None),
        )

        # Add computed column so we can filter and order by it.
        stmt = stmt.add_columns(distance_col)
        stmt = stmt.where(distance_col <= params.radius_km)
        stmt = stmt.order_by(distance_col)
    else:
        stmt = stmt.order_by(Venue.name)

    # COUNT before LIMIT/OFFSET
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    # Pagination
    offset = (params.page - 1) * params.per_page
    stmt = stmt.offset(offset).limit(params.per_page)

    rows = await db.execute(stmt)

    if distance_col is not None:
        # When extra column is added, rows contain (Venue, distance_km) tuples.
        items: list[Venue] = [row[0] for row in rows.all()]
    else:
        items = list(rows.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": params.page,
        "per_page": params.per_page,
    }
