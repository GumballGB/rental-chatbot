# Testing file dedicated into testing the store.py functionality

import json

import pytest

from core.store import JsonStore, NotFoundError


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

def test_get_happy_listing():

    store = JsonStore()

    listing_id = store.get_listing("LST-001")
    assert listing_id.listing_id == "LST-001"


def test_get_faulty_listing():

    store = JsonStore()

    with pytest.raises(NotFoundError) as exc_info:
        store.get_listing("LST-999")

    assert str(exc_info.value) == (
        "Listing with id LST-999 not found."
    )

def test_get_happy_building():

    store = JsonStore()

    building_id = store.get_building("BLD-001")
    assert building_id.building_id == "BLD-001"

def test_get_faulty_building():

    store = JsonStore()

    with pytest.raises(NotFoundError) as exc_info:
        store.get_building("BLD-999")

    assert str(exc_info.value) == (
        "Building with id BLD-999 not found."
    )

def test_get_happy_location():
    
    store = JsonStore()

    location_id = store.get_location("LOC-001")
    assert location_id.location_id == "LOC-001"

def test_get_faulty_location():

    store = JsonStore()

    with pytest.raises(NotFoundError) as exc_info:
        store.get_location("LOC-999")

    assert str(exc_info.value) == (
        "Location with id LOC-999 not found."
    )