# Data access layer for the application. This module provides functions
# to interact with the data. This is supposed to be read-only.
# By design, the store will fetch all the data at once, ready to go, from memory.

import json
import os
import unicodedata
from typing import Any

from models.building import Building
from models.listings import Listing
from models.location import Location

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")


def normalize_name(value: str) -> str:
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(character)
    )
    return " ".join(
        "".join(
            character if character.isalnum() else " " for character in value
        ).split()
    )


class NotFoundError(Exception):
    """Raised when a lookup is given an id that does not exist in the store."""


class JsonStore:
    """
    A class to handle reading JSON data for the application.
    """

    def __init__(self, data_dir=DATA_DIR):
        """
        Initialize the JsonStore with the directory where JSON files are stored.
        Convert all JSON files to Pydantic models and validate them.
        The reason that everything gets converted to Pydantic models is that we want
        to ensure that the data is valid and has the correct structure.
        Also, the dataset is small, so we can afford to load everything into memory at once.
        """

        self.data_dir = data_dir

        # For each record, turn them into a model object

        # Create empty dictionaries to hold the data
        self.buildings: dict[str, Building] = {}
        self.listings: dict[str, Listing] = {}
        self.locations: dict[str, Location] = {}

        for n in ["buildings.json", "listings.json", "locations.json"]:
            data = self.load_data(n)

            if n == "buildings.json":
                for d in data:
                    building = Building.model_validate(d)
                    self.buildings[building.building_id] = building

            elif n == "listings.json":
                for d in data:
                    listing = Listing.model_validate(d)
                    self.listings[listing.listing_id] = listing

            elif n == "locations.json":
                for d in data:
                    loc = Location.model_validate(d)
                    self.locations[loc.location_id] = loc

    # Helper function to load data from a JSON file
    def load_data(self, filename: str) -> list[dict[str, Any]]:
        """
        Load data from a JSON file.

        :param filename: Name of the JSON file to load.
        :return: List of dictionaries containing the data.
        """
        file_path = os.path.join(self.data_dir, filename)
        with open(file_path, "r") as f:
            return json.load(f)

    # Main Getters

    def get_listing(self, listing_id: str) -> Listing:
        """
        Get a listing by its ID.

        :param listing_id: The ID of the listing to retrieve.
        :return: The Listing object corresponding to the given ID.
        :raises NotFoundError: If the listing with the given ID does not exist.
        """
        if listing_id in self.listings:
            return self.listings[listing_id]
        else:
            raise NotFoundError(f"Listing with id {listing_id} not found.")

    def get_building(self, building_id: str) -> Building:
        """
        Get a building by its ID.

        :param building_id: The ID of the building to retrieve.
        :return: The Building object corresponding to the given ID.
        :raises NotFoundError: If the building with the given ID does not exist.
        """
        if building_id in self.buildings:
            return self.buildings[building_id]
        else:
            raise NotFoundError(f"Building with id {building_id} not found.")

    def get_location(self, location_id: str) -> Location:
        """
        Get a location by its ID.

        :param location_id: The ID of the location to retrieve.
        :return: The Location object corresponding to the given ID.
        :raises NotFoundError: If the location with the given ID does not exist.
        """
        if location_id in self.locations:
            return self.locations[location_id]
        else:
            raise NotFoundError(f"Location with id {location_id} not found.")

    # Return the list of listing as objects
    def get_listing_object_per_building(self, building_id) -> dict[str, Listing]:
        """
        Get the number of listings per building.

        :return: A dictionary where keys are listing IDs and values are Listing objects for the given building ID.
        :raises NotFoundError: If the building with the given ID does not exist.
        """
        listings_per_building = {}

        # Check if the building exists
        if building_id not in self.buildings:
            raise NotFoundError(f"Building with id {building_id} not found.")

        for listing in self.listings.values():
            if listing.building_id == building_id:
                listings_per_building[listing.listing_id] = listing

        return listings_per_building

    # Return the list of buildings in a location as objects
    def get_building_object_per_location(self, location_id) -> dict[str, Building]:
        """
        Get the number of buildings per location.

        :return: A dictionary where keys are building IDs and values are Building objects for the given location ID.
        :raises NotFoundError: If the location with the given ID does not exist.
        """
        buildings_per_location = {}

        # Check if the location exists
        if location_id not in self.locations:
            raise NotFoundError(f"Location with id {location_id} not found.")

        for building in self.buildings.values():
            if building.location_id == location_id:
                buildings_per_location[building.building_id] = building

        return buildings_per_location

    # Finder for a location, not that locations can have alternative names
    # Note that accents are a thing, for Montreal and Copenhagen names (like Montréal and København)
    def find_location(self, name: str) -> Location:
        """
        Find a location by its name or alternative names.

        :param name: The name of the location to find.
        :return: The Location object corresponding to the given name.
        :raises NotFoundError: If no location with the given name exists.
        """

        # Normalize the input name to handle accents and alternative spellings
        normalized_name = normalize_name(name)
        if not normalized_name:
            raise NotFoundError(f"Location with name {name} not found.")

        # Prepare a list of normalized location names for comparison
        normalized_locations = [
            (
                location,
                [
                    normalize_name(location_name)
                    for location_name in [
                        location.name,
                        *(location.alternative_names or []),
                    ]
                ],
            )
            for location in self.locations.values()
        ]

        for location, location_names in normalized_locations:
            if normalized_name in location_names:
                return location

        for location, location_names in normalized_locations:
            if any(
                normalized_name in location_name for location_name in location_names
            ):
                return location

        raise NotFoundError(f"Location with name {name} not found.")

    # The ultimate search function for listings with various filters
    def search_listings(
        self,
        location_name: str | None = None,
        building_name: str | None = None,
        min_rent: int | None = None,
        max_rent: int | None = None,
        currency: str | None = None,
        bedrooms: float | None = None,
        pets_allowed: bool | None = None,
        available_only: bool = True,
        sort_by: str | None = None,
        limit: int = 5,
    ) -> list[Listing]:
        """
        Search for listings based on various filters.

        :param location_name: The name of the location to filter by.
        :param building_name: The name of the building to filter by.
        :param min_rent: The minimum monthly rent to filter by.
        :param max_rent: The maximum monthly rent to filter by.
        :param currency: The currency used for rent filters.
        :param bedrooms: The number of bedrooms to filter by.
        :param pets_allowed: Whether pets are allowed to filter by.
        :param available_only: Whether to only include available listings.
        :param sort_by: Optional result ordering, such as rent_asc or rent_desc.
        :param limit: The maximum number of listings to return.
        :return: A list of Listing objects matching the filters.
        :raises ValueError: If min_rent is greater than max_rent.
        """

        # Check the basic stuff
        if min_rent is not None and max_rent is not None and min_rent > max_rent:
            raise ValueError("min_rent cannot be greater than max_rent.")
        uses_rent = (
            min_rent is not None
            or max_rent is not None
            or sort_by in {"rent_asc", "rent_desc"}
        )
        if uses_rent and currency is None:
            raise ValueError("currency is required when filtering or sorting by rent.")

        if sort_by not in {None, "rent_asc", "rent_desc"}:
            raise ValueError("sort_by must be rent_asc or rent_desc.")

        if currency is not None:
            currency = currency.upper()
            if currency not in {"CAD", "DKK"}:
                raise ValueError("currency must be CAD or DKK.")

        limit = max(1, min(limit, 6))

        location_id = None
        if location_name is not None:
            location_id = self.find_location(location_name).location_id

        normalized_building_name = (
            normalize_name(building_name) if building_name is not None else None
        )

        matching_building_ids = {
            building.building_id
            for building in self.buildings.values()
            if (location_id is None or building.location_id == location_id)
            and (
                normalized_building_name is None
                or normalized_building_name in normalize_name(building.name)
            )
        }

        matches = []
        for listing in self.listings.values():
            if listing.building_id not in matching_building_ids:
                continue
            if min_rent is not None and listing.monthly_rent < min_rent:
                continue
            if max_rent is not None and listing.monthly_rent > max_rent:
                continue
            if currency is not None and listing.currency != currency:
                continue
            if bedrooms is not None and listing.bedrooms != bedrooms:
                continue
            if pets_allowed is not None and listing.pets_allowed != pets_allowed:
                continue
            if available_only and listing.availability_status != "available":
                continue

            matches.append(listing)

        if sort_by == "rent_asc":
            matches.sort(key=lambda listing: listing.monthly_rent)
        elif sort_by == "rent_desc":
            matches.sort(key=lambda listing: listing.monthly_rent, reverse=True)

        return matches[:limit]
