# Testing file dedicated into testing the tools.py functionality

import json

from core.store import JsonStore, normalize_name
from core.tools import (
    CHATBOT_SCHEMA_LIST,
    TRIAGE_SCHEMA_LIST,
    find_duplicate_enquiry_candidates,
    get_building,
    get_enquiry,
    get_listing,
    get_location_by_name,
    run_tool,
    search_listings,
)

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

    result = run_tool(
        "get_listing",
        store,
        {"get_listing"},
        listing_id=listing_id,
    )
    result_json = json.loads(result)

    assert result_json["listing_id"] == "LST-001"
    assert result_json["bedrooms"] == 0.0
    assert result_json["bathrooms"] == 1.0
    assert result_json["building_id"] == "BLD-001"

# Unhappy path test for run_tool with get_listing
def test_run_tool_get_listing_not_found():

    store = JsonStore()
    listing_id = "LST-999"

    result = run_tool(
        "get_listing",
        store,
        {"get_listing"},
        listing_id=listing_id,
    )
    result_json = json.loads(result)

    assert "error" in result_json
    assert result_json["error"] == f"Listing with id {listing_id} not found."

# Faulty test with a missing argument for get_listing
def test_run_tool_get_listing_missing_argument():

    store = JsonStore()

    result = run_tool("get_listing", store, {"get_listing"})
    result_json = json.loads(result)

    assert "error" in result_json

# Faulty path with an uknown tool name
def test_run_tool_unknown_tool():

    store = JsonStore()

    result = run_tool("unknown_tool", store, {"unknown_tool"})
    result_json = json.loads(result)

    assert "error" in result_json
    assert result_json["error"] == "Tool unknown_tool not found."

# Test for get_location_by_name with an alternative name
def test_get_location_by_alternative_name():
    result = get_location_by_name(JsonStore(), "rosemont")
    result_json = json.loads(result)

    assert result_json["location_id"] == "LOC-009"
    assert result_json["name"] == "Rosemont–La Petite-Patrie"

# Test a location with an accent
def test_get_location_with_accent():
    result = get_location_by_name(JsonStore(), "Montreal")
    result_json = json.loads(result)

    assert normalize_name("Montréal") == "montreal"
    assert result_json["location_id"] == "LOC-002"
    assert result_json["name"] == "Downtown Montreal"

# Test for search_listings by location and rent range
def test_search_listings_by_location_and_rent_range():
    result = search_listings(
        JsonStore(),
        location_name="Verdun",
        min_rent=1500,
        max_rent=1700,
        currency="CAD",
    )
    result_json = json.loads(result)

    assert result_json["count"] == 1
    assert result_json["listings"][0]["listing_id"] == "LST-037"
    assert result_json["listings"][0]["monthly_rent"] == 1655
    assert result_json["listings"][0]["location_name"] == "Verdun"


def test_search_listings_requires_currency_for_rent_filter():
    result = search_listings(JsonStore(), max_rent=9000, limit=100)
    result_json = json.loads(result)

    assert result_json == {
        "error": "currency is required when filtering or sorting by rent."
    }


def test_search_listings_filters_currency_and_clamps_limit():
    result = search_listings(
        JsonStore(),
        max_rent=9000,
        currency="CAD",
        limit=100,
    )
    result_json = json.loads(result)

    assert result_json["count"] == 6
    assert all(
        listing["currency"] == "CAD"
        for listing in result_json["listings"]
    )


def test_search_listings_requires_currency_for_rent_sorting():
    result = search_listings(JsonStore(), sort_by="rent_asc")

    assert json.loads(result) == {
        "error": "currency is required when filtering or sorting by rent."
    }


def test_search_listings_sorts_all_matches_before_limit():
    store = JsonStore()
    result = search_listings(
        store,
        currency="CAD",
        sort_by="rent_asc",
        limit=6,
    )
    result_json = json.loads(result)
    expected_rents = sorted(
        listing.monthly_rent
        for listing in store.listings.values()
        if listing.currency == "CAD"
        and listing.availability_status == "available"
    )[:6]

    assert [
        listing["monthly_rent"]
        for listing in result_json["listings"]
    ] == expected_rents


def test_get_enquiry_tool_returns_serialized_enquiry():
    result = json.loads(get_enquiry(JsonStore(), "ENQ-001"))

    assert result["enquiry_id"] == "ENQ-001"
    assert result["email"] == "alex.morgan@example.com"


def test_find_duplicate_candidates_tool_excludes_current_enquiry():
    result = json.loads(
        find_duplicate_enquiry_candidates(
            JsonStore(),
            exclude_enquiry_id="ENQ-011",
            received_before="2026-10-24",
            email="alex.morgan@example.com",
        )
    )

    assert result["count"] == 1
    assert result["candidates"][0]["enquiry_id"] == "ENQ-001"
    assert result["candidates"][0]["matched_on"] == ["email"]


def test_enquiry_history_tools_are_only_exposed_to_triage():
    chatbot_tool_names = {schema["name"] for schema in CHATBOT_SCHEMA_LIST}
    triage_tool_names = {schema["name"] for schema in TRIAGE_SCHEMA_LIST}

    assert "get_enquiry" not in chatbot_tool_names
    assert "find_duplicate_enquiry_candidates" not in chatbot_tool_names
    assert "get_enquiry" in triage_tool_names
    assert "find_duplicate_enquiry_candidates" in triage_tool_names


def test_dispatcher_denies_enquiry_tool_for_chatbot():
    allowed_tool_names = {schema["name"] for schema in CHATBOT_SCHEMA_LIST}
    result = run_tool(
        "get_enquiry",
        JsonStore(),
        allowed_tool_names,
        enquiry_id="ENQ-001",
    )

    assert json.loads(result) == {"error": "Tool get_enquiry is not allowed."}
