# Data access layer for the application. This module provides functions 
# to interact with the data. This is supposed to be read-only.
# By design, the store will fetch all the data at once, ready to go, from memory.

import json
import os
from typing import Any

from models.building import Building
from models.listings import Listing
from models.location import Location

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")

class NotFoundError(Exception):
    """Raised when a lookup is given an id that does not exist in the store."""


class JsonStore:
    """
    A class to handle reading JSON data for the application.
    """

    def __init__(self, data_dir = DATA_DIR):
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
        with open(file_path, 'r') as f:
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


