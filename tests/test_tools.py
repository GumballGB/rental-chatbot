# Testing file dedicated into testing the tools.py functionality

import json

from core.store import JsonStore
from core.tools import get_listing

# Happy path test for get_listing, take listing LST-001
def test_get_listing_happy_path():
    store = JsonStore()
    listing_id = "LST-001"


    result = get_listing(store, listing_id)
    result_json = json.loads(result)

    assert result_json["listing_id"] == "LST-001"
    assert result_json["bedrooms"] == 0.0
    assert result_json["bathrooms"] == 1.0
    assert result_json["building_id"] == "BLD-001"

# Unhappy path test for get_listing
def test_get_listing_not_found():
    store = JsonStore()
    listing_id = "LST-999"

    result = get_listing(store, listing_id)
    result_json = json.loads(result)

    assert "error" in result_json
    assert result_json["error"] == f"Listing with id {listing_id} not found."