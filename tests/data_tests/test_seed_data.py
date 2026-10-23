# The goal of this document is to check the validity of the seed data for the rental chatbot application. 
# The seed data is stored in a JSON file and contains information about buildings and unit enquiries. 
# This test will ensure that the data adheres to the defined Pydantic models and meets the required constraints.
# Also, this seed data was generated using ChatGPT

import json

import pytest
from pydantic import ValidationError

from models.building import Building
from models.listings import Listing
from models.location import Location


def test_seed_location_data():

    with open('data/locations.json') as f:
        location_data = json.load(f)
    
    for location in location_data:
        try:
            Location(**location)
        except ValidationError as e:

            # If something fails, we want to know which location data caused the failure.
            location_id = location.get('location_id')

            assert False, f"Location data validation failed: {e}, Location ID: {location_id}"


def test_seed_building_data():

    with open('data/buildings.json') as f:
        building_data = json.load(f)
    
    for building in building_data:
        try:
            Building(**building)
        except ValidationError as e:

            building_id = building.get('building_id')

            assert False, f"Building data validation failed: {e}, Building ID: {building_id}"


def test_seed_listings_data():

    with open('data/listings.json') as f:
        listings_data = json.load(f)
    
    for listing in listings_data:
        try:
            # Assuming Listing is another Pydantic model defined in your application
            Listing(**listing)
        except ValidationError as e:

            listing_id = listing.get('listing_id')

            assert False, f"Listings data validation failed: {e}, Listing ID: {listing_id}"

@pytest.mark.parametrize(
    "filename, id_field",
    [
        ("locations.json", "location_id"),
        ("buildings.json", "building_id"),
        ("listings.json", "listing_id"),
    ]
)

def test_seed_data_duplicates(filename, id_field):

    with open(f"data/{filename}") as f:
        data = json.load(f)

    seen_ids = set()
    duplicate_ids = set()

    for item in data:
        item_id = item[id_field]

        if item_id in seen_ids:
            duplicate_ids.add(item_id)

        seen_ids.add(item_id)

    assert not duplicate_ids, (
        f"Duplicate {id_field} values in {filename}: "
        f"{sorted(duplicate_ids)}"
    )


# Check that the seed data's id exists
@pytest.mark.parametrize(
    "filename, id_field",
    [
        ("locations.json", "location_id"),
        ("buildings.json", "building_id"),
        ("listings.json", "listing_id"),
    ]
)
def test_seed_data_id_exists(filename, id_field):

    with open(f"data/{filename}") as f:
        data = json.load(f)

    for item in data:
        item_id = item.get(id_field)

        assert item_id is not None, (
            f"{id_field} is missing in {filename}: {item}"
        )

# Check for referential integrity between buildings and locations
def test_building_location_referential_integrity():
    with open("data/buildings.json") as f:
        building_data = json.load(f)

    with open("data/locations.json") as f:
        location_data = json.load(f)

    location_ids = {location["location_id"] for location in location_data}

    for building in building_data:
        building_location_id = building.get("location_id")

        assert building_location_id in location_ids, (
            f"Building {building['building_id']} references a non-existent "
            f"location_id: {building_location_id}"
        )

# Check for referential integrity between listings and buildings
def test_listing_building_referential_integrity():
    with open("data/listings.json") as f:
        listings_data = json.load(f)

    with open("data/buildings.json") as f:
        building_data = json.load(f)

    building_ids = {building["building_id"] for building in building_data}

    for listing in listings_data:
        listing_building_id = listing.get("building_id")

        assert listing_building_id in building_ids, (
            f"Listing {listing['listing_id']} references a non-existent "
            f"building_id: {listing_building_id}"
        )