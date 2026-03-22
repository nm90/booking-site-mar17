"""
Property Model - Handles property data validation and database operations.

MVC Role: MODEL
- Validates property input (name, location, capacity, price)
- Manages database queries for properties table
- Returns data structures (dicts) to controllers
"""

from typing import Dict, List, Optional
from backend.database.connection import execute_query


class Property:
    """Property model for managing vacation rental listings."""

    VALID_STATUSES = ['active', 'inactive', 'maintenance']

    @staticmethod
    def validate(name: str, location: str, capacity, price_per_night, status: str = None) -> None:
        """Validate property data. Raises ValueError if invalid."""
        if not name or not name.strip():
            raise ValueError("Property name is required")

        if not location or not location.strip():
            raise ValueError("Location is required")

        try:
            capacity_int = int(capacity)
        except (TypeError, ValueError):
            raise ValueError("Capacity must be a whole number")

        if capacity_int < 1:
            raise ValueError("Capacity must be at least 1")

        try:
            price = float(price_per_night)
        except (TypeError, ValueError):
            raise ValueError("Price per night must be a number")

        if price <= 0:
            raise ValueError("Price per night must be greater than 0")

        if status is not None and status not in Property.VALID_STATUSES:
            raise ValueError(f"Status must be one of {Property.VALID_STATUSES}")

    @staticmethod
    def create(name: str, description: str, location: str,
               capacity: int, price_per_night: float) -> Dict:
        """Create a new property and return it."""
        Property.validate(name, location, capacity, price_per_night)

        query = """
            INSERT INTO properties (name, description, location, capacity, price_per_night)
            VALUES (?, ?, ?, ?, ?)
        """
        property_id = execute_query(
            query,
            (name.strip(), (description or '').strip() or None, location.strip(),
             int(capacity), float(price_per_night)),
            commit=True
        )
        return Property.get_by_id(property_id)

    @staticmethod
    def get_by_id(property_id: int) -> Optional[Dict]:
        """Fetch a property by its ID."""
        return execute_query(
            "SELECT * FROM properties WHERE id = ?",
            (property_id,), fetch_one=True
        )

    @staticmethod
    def get_all(active_only: bool = False) -> List[Dict]:
        """Fetch all properties, optionally filtered to active only."""
        if active_only:
            query = "SELECT * FROM properties WHERE status = 'active' ORDER BY name"
        else:
            query = "SELECT * FROM properties ORDER BY name"
        result = execute_query(query, fetch_all=True)
        return result if result else []

    @staticmethod
    def update(property_id: int, name: str, description: str, location: str,
               capacity: int, price_per_night: float, status: str) -> Optional[Dict]:
        """Update a property and return the updated row."""
        Property.validate(name, location, capacity, price_per_night, status)

        query = """
            UPDATE properties
            SET name = ?, description = ?, location = ?, capacity = ?,
                price_per_night = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        execute_query(
            query,
            (name.strip(), (description or '').strip() or None, location.strip(),
             int(capacity), float(price_per_night), status, property_id),
            commit=True
        )
        return Property.get_by_id(property_id)

    @staticmethod
    def delete(property_id: int) -> bool:
        """Delete a property if it has no active/pending bookings."""
        active_bookings = execute_query(
            "SELECT COUNT(*) as cnt FROM bookings WHERE property_id = ? AND status IN ('pending', 'approved')",
            (property_id,), fetch_one=True
        )
        if active_bookings and active_bookings['cnt'] > 0:
            raise ValueError("Cannot delete a property with active or pending bookings")

        execute_query("DELETE FROM properties WHERE id = ?", (property_id,), commit=True)
        return True
