# Testing file dedicated into testing the store.py functionality

from core.store import JsonStore
import json

# count the number of listing in the JSON
def count_num():

    # get the count of the listings
    with open('data/listings.json') as f:
        listings_data = json.load(f)
        num_listings = len(listings_data)

    with open('data/buildings.json') as f:
        buildings_data = json.load(f)
        num_buildings = len(buildings_data)

    with open('data/locations.json') as f:
        locations_data = json.load(f)
        num_locations = len(locations_data)

    return num_listings, num_buildings, num_locations


def test_store():

    # Initiate the store class with the data directory
    store = JsonStore()

    # count the number of listings, buildings, and locations in the JSON files
    num_listings, num_buildings, num_locations = count_num()

    # Check if the data is loaded correctly
    assert isinstance(store.buildings, dict)
    assert isinstance(store.listings, dict)
    assert isinstance(store.locations, dict)

    # Check if the data is not empty
    assert len(store.buildings) == num_buildings
    assert len(store.listings) == num_listings
    assert len(store.locations) == num_locations