# Testing file dedicated into testing the tools.py functionality

import json

from core.store import JsonStore
from core.tools import get_building, get_listing, run_tool

# Pretty much all test uses JsonStore, so let's initialize it first
# @pytest.fixture
# def store():
#     return JsonStore()


# Happy path test for get_listing, take listing LST-001
def test_get_listing_happy_path():
    listing_id = "LST-001"
    store = JsonStore()

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

# Happy path test for get_building
def test_get_building_happy_path():
    store = JsonStore()
    building_id = "BLD-001"

    result = get_building(store, building_id)
    result_json = json.loads(result)

    assert result_json["building_id"] == "BLD-001"
    assert result_json["address"] == "101 Rue Exemple-Canal, Montréal (fictional)"
    assert result_json["number_of_units"] == 86

# Unhappy path test for get_building
def test_get_building_not_found():
    store = JsonStore()
    building_id = "BLD-999"

    result = get_building(store, building_id)
    result_json = json.loads(result)

    assert "error" in result_json
    assert result_json["error"] == f"Building with id {building_id} not found."

# Testing case for run_tool

# Happy path test for run_tool with get_listing
def test_run_tool_get_listing_happy_path():

    store = JsonStore()
    listing_id = "LST-001"

    result = run_tool("get_listing", store, listing_id=listing_id)
    result_json = json.loads(result)

    assert result_json["listing_id"] == "LST-001"
    assert result_json["bedrooms"] == 0.0
    assert result_json["bathrooms"] == 1.0
    assert result_json["building_id"] == "BLD-001"

# Unhappy path test for run_tool with get_listing
def test_run_tool_get_listing_not_found():

    store = JsonStore()
    listing_id = "LST-999"

    result = run_tool("get_listing", store, listing_id=listing_id)
    result_json = json.loads(result)

    assert "error" in result_json
    assert result_json["error"] == f"Listing with id {listing_id} not found."

# Faulty test with a missing argument for get_listing
def test_run_tool_get_listing_missing_argument():

    store = JsonStore()

    result = run_tool("get_listing", store)
    result_json = json.loads(result)

    assert "error" in result_json

# Faulty path with an uknown tool name
def test_run_tool_unknown_tool():

    store = JsonStore()

    result = run_tool("unknown_tool", store)
    result_json = json.loads(result)

    assert "error" in result_json
    assert result_json["error"] == "Tool unknown_tool not found."