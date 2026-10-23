# Data access layer for the application. This module provides functions 
# to interact with the data. This is supposed to be read-only.
# By design, the store will fetch all the data at once, ready to go, from memory.

import os
import json
from typing import List, Dict, Any
from models.building import Building
from models.listings import Listing
from models.location import Location

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")

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
        self.buildings: Dict[str, Building] = {}
        self.listings: Dict[str, Listing] = {}
        self.locations: Dict[str, Location] = {}

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
    def load_data(self, filename: str) -> List[Dict[str, Any]]:
        """
        Load data from a JSON file.

        :param filename: Name of the JSON file to load.
        :return: List of dictionaries containing the data.
        """
        file_path = os.path.join(self.data_dir, filename)
        with open(file_path, 'r') as f:
            return json.load(f)
