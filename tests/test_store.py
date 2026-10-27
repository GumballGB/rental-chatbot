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

def count_num_listings_per_building(building_id):

    with open('data/listings.json') as f:
        listings_data = json.load(f)
        num_listings = sum(1 for listing in listings_data if listing['building_id'] == building_id)

    return num_listings

def count_num_buildings_per_location(location_id):

    with open('data/buildings.json') as f:
        buildings_data = json.load(f)
        num_buildings = sum(1 for building in buildings_data if building['location_id'] == location_id)

    return num_buildings

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


def test_get_enquiry_by_id():
    enquiry = JsonStore().get_enquiry("ENQ-001")

    assert enquiry.name == "Alex Morgan"
    assert enquiry.email == "alex.morgan@example.com"


def test_find_duplicate_candidates_excludes_current_enquiry():
    candidates = JsonStore().find_duplicate_enquiry_candidates(
        exclude_enquiry_id="ENQ-011",
        received_before="2026-10-24",
        email="alex.morgan@example.com",
        phone="+1-514-555-0101",
    )

    assert [enquiry.enquiry_id for enquiry, _ in candidates] == ["ENQ-001"]
    assert candidates[0][1] == ["email", "phone"]


def test_find_duplicate_candidates_uses_phone_without_email():
    candidates = JsonStore().find_duplicate_enquiry_candidates(
        exclude_enquiry_id="ENQ-011",
        received_before="2026-10-24",
        phone="5145550101",
    )

    assert [enquiry.enquiry_id for enquiry, _ in candidates] == ["ENQ-001"]


def test_original_enquiry_does_not_match_later_follow_up():
    candidates = JsonStore().find_duplicate_enquiry_candidates(
        exclude_enquiry_id="ENQ-001",
        received_before="2026-10-20",
        email="alex.morgan@example.com",
        phone="+1-514-555-0101",
    )

    assert candidates == []


def test_duplicate_candidates_exclude_same_day_enquiries():
    candidates = JsonStore().find_duplicate_enquiry_candidates(
        exclude_enquiry_id="ENQ-CURRENT",
        received_before="2026-10-20",
        email="alex.morgan@example.com",
    )

    assert candidates == []

# Test getting all listings as objects from a building
def test_get_listings_from_building():

    store = JsonStore()

    # This will be hardcoded for now, assuming "BLD-001" exists in the test data
    building_id = "BLD-001"

    listings = store.get_listing_object_per_building(building_id)

    for listing in listings.values():
        assert listing.building_id == building_id

    # Check if the number of listings matches the expected count
    expected_num_listings = count_num_listings_per_building(building_id)
    assert len(listings) == expected_num_listings


# Test getting all listings as objects from a non-existent building
def test_get_listings_from_nonexistent_building():

    store = JsonStore()

    building_id = "BLD-999"

    with pytest.raises(NotFoundError) as exc_info:
        store.get_listing_object_per_building(building_id)

    assert str(exc_info.value) == (
        "Building with id BLD-999 not found."
    )

# Test getting buildings from a location
def test_get_buildings_from_location():

    store = JsonStore()

    location_id = "LOC-001"

    buildings = store.get_building_object_per_location(location_id)

    for building in buildings.values():
        assert building.location_id == location_id

    # Check if the number of buildings matches the expected count
    expected_num_buildings = count_num_buildings_per_location(location_id)
    assert len(buildings) == expected_num_buildings

# Test getting buildings from a non-existent location
def test_get_buildings_from_nonexistent_location():

    store = JsonStore()

    location_id = "LOC-999"

    with pytest.raises(NotFoundError) as exc_info:
        store.get_building_object_per_location(location_id)

    assert str(exc_info.value) == (
        "Location with id LOC-999 not found."
    )
