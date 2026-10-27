# The tools file is similar to the controllers found in Java

import json

from core.store import JsonStore, NotFoundError

### MAIN TOOLS ###

# tool functions for getting a listing
def get_listing(store: JsonStore, listing_id: str) -> str:
    """
    Get a listing from the store and return it as a JSON string.

    Args:
        store (JsonStore): The JSON store instance.
        listing_id (str): The ID of the listing to retrieve.

    Returns:
        str: The JSON string representation of the listing or an error message.
    """

    try:
        # Get the pydantic listing obj. from the JSON store
        listing = store.get_listing(listing_id)

        # Convert the listing into pure JSON
        listing_json = listing.model_dump_json()

        return listing_json

    except NotFoundError as e:
        # JSON-ify the error message
        error_json = {"error": str(e)}

        return json.dumps(error_json)


GET_LISTING_SCHEMA = {
    "name": "get_listing",
    "description": "Get a listing from its ID. The listing ID is always LST- with a unique identifier. For example, LST-123. "
    "When getting a listing ID, it allows to get more information about the listing itself, like the bedroom count, bathroom count, and other details.",
    "input_schema": {
        "type": "object",
        "properties": {
            "listing_id": {
                "type": "string",
                "description": "The ID of the listing to retrieve.",
            }
        },
    },
}


def get_building(store: JsonStore, building_id: str) -> str:
    """
    Get a building from the store and return it as a JSON string.

    Args:
        store (JsonStore): The JSON store instance.
        building_id (str): The ID of the building to retrieve.

    Returns:
        str: The JSON string representation of the building or an error message.
    """

    try:
        building = store.get_building(building_id)
        building_json = building.model_dump_json()
        return building_json
    except NotFoundError as e:
        error_json = {"error": str(e)}
        return json.dumps(error_json)


GET_BUILDING_SCHEMA = {
    "name": "get_building",
    "description": "Get a building from its ID. The building ID is always BLD- with a unique identifier. For example, BLD-123. "
    "When getting a building ID, it allows to get more information about the building itself, like the address, number of units, and other details.",
    "input_schema": {
        "type": "object",
        "properties": {
            "building_id": {
                "type": "string",
                "description": "The ID of the building to retrieve.",
            }
        },
    },
}


def get_location_by_name(store: JsonStore, name: str) -> str:
    try:
        return store.find_location(name).model_dump_json()
    except NotFoundError as e:
        return json.dumps({"error": str(e)})


GET_LOCATION_BY_NAME_SCHEMA = {
    "name": "get_location_by_name",
    "description": "Find a rental location or neighbourhood by its common or alternative name.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "A location name such as Verdun, Rosemont, or Montreal.",
            }
        },
        "required": ["name"],
    },
}

### SEARCH TOOLS ###

def search_listings(store: JsonStore, **filters) -> str:
    try:
        listings = store.search_listings(**filters)
    except (NotFoundError, ValueError) as e:
        return json.dumps({"error": str(e)})

    results = []
    for listing in listings:
        building = store.get_building(listing.building_id)
        location = store.get_location(building.location_id)
        results.append(
            {
                "listing_id": listing.listing_id,
                "listing_name": listing.listing_name,
                "monthly_rent": listing.monthly_rent,
                "currency": listing.currency,
                "bedrooms": listing.bedrooms,
                "bathrooms": listing.bathrooms,
                "layout": listing.layout,
                "availability_status": listing.availability_status,
                "available_date": (
                    listing.available_date.isoformat()
                    if listing.available_date is not None
                    else None
                ),
                "pets_allowed": listing.pets_allowed,
                "building_id": building.building_id,
                "building_name": building.name,
                "location_id": location.location_id,
                "location_name": location.name,
            }
        )

    return json.dumps({"count": len(results), "listings": results})


SEARCH_LISTINGS_SCHEMA = {
    "name": "search_listings",
    "description": "Search available rental listings using natural criteria. Use this when the user does not provide a listing ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location_name": {
                "type": "string",
                "description": "Neighbourhood or location name.",
            },
            "building_name": {
                "type": "string",
                "description": "Full or partial building name.",
            },
            "min_rent": {"type": "integer", "minimum": 0},
            "max_rent": {"type": "integer", "minimum": 0},
            "currency": {
                "type": "string",
                "enum": ["CAD", "DKK"],
                "description": "Required when min_rent or max_rent is provided.",
            },
            "bedrooms": {"type": "number", "minimum": 0},
            "pets_allowed": {"type": "boolean"},
            "available_only": {"type": "boolean", "default": True},
            "sort_by": {
                "type": "string",
                "enum": ["rent_asc", "rent_desc"],
                "description": "Sort by lowest or highest monthly rent. Requires currency.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 6, "default": 5},
        },
    },
}

### ENQUIRY TOOLS ###

# generic enquiry retrieval tool for getting an enquiry
def get_enquiry(store: JsonStore, enquiry_id: str) -> str:
    try:
        return store.get_enquiry(enquiry_id).model_dump_json()
    except NotFoundError as error:
        return json.dumps({"error": str(error)})


GET_ENQUIRY_SCHEMA = {
    "name": "get_enquiry",
    "description": "Retrieve one historical rental enquiry by its exact enquiry ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "enquiry_id": {
                "type": "string",
                "description": "The exact enquiry ID to retrieve.",
            }
        },
        "required": ["enquiry_id"],
    },
}

# Specific tool for finding potential duplicate enquiries
def find_duplicate_enquiry_candidates(
    store: JsonStore,
    exclude_enquiry_id: str,
    received_before: str,
    email: str | None = None,
    phone: str | None = None,
    name: str | None = None,
    listing_id: str | None = None,
    move_in_date: str | None = None,
) -> str:
    """
    Find potential duplicate enquiries based on email, phone, name, listing ID, and move-in date.

    Args:
        store (JsonStore): The JSON store containing enquiries.
        exclude_enquiry_id (str): The enquiry ID to exclude from the search.
        email (str | None): The email to match.
        phone (str | None): The phone number to match.
        name (str | None): The name to match.
        listing_id (str | None): The listing ID to match.
        move_in_date (str | None): The move-in date to match.

    Returns:
        str: A JSON string containing the count and list of candidate enquiries.
    """
    try:

        candidates = store.find_duplicate_enquiry_candidates(
            exclude_enquiry_id=exclude_enquiry_id,
            received_before=received_before,
            email=email,
            phone=phone,
            name=name,
            listing_id=listing_id,
            move_in_date=move_in_date,
        )
    except ValueError as error:
        return json.dumps({"error": str(error)})

    return json.dumps(
        {
            "count": len(candidates),
            "candidates": [
                {
                    **enquiry.model_dump(mode="json"),
                    "matched_on": matched_on,
                }
                for enquiry, matched_on in candidates
            ],
        }
    )


FIND_DUPLICATE_ENQUIRY_CANDIDATES_SCHEMA = {
    "name": "find_duplicate_enquiry_candidates",
    "description": (
        "Find historical enquiries that may duplicate the current enquiry. "
        "Always exclude the enquiry currently being triaged."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "name": {"type": "string"},
            "listing_id": {"type": "string"},
            "move_in_date": {"type": "string"},
        },
    },
}

# List of schemas for different tool categories

CHATBOT_SCHEMA_LIST = [
    GET_LISTING_SCHEMA,
    GET_BUILDING_SCHEMA,
    GET_LOCATION_BY_NAME_SCHEMA,
    SEARCH_LISTINGS_SCHEMA,
]

TRIAGE_SCHEMA_LIST = [
    GET_LISTING_SCHEMA,
    GET_BUILDING_SCHEMA,
    GET_LOCATION_BY_NAME_SCHEMA,
    GET_ENQUIRY_SCHEMA,
    FIND_DUPLICATE_ENQUIRY_CANDIDATES_SCHEMA,
]

# Lookup dict
LOOKUP_DICT = {
    "get_listing": get_listing,
    "get_building": get_building,
    "get_location_by_name": get_location_by_name,
    "search_listings": search_listings,
    "get_enquiry": get_enquiry,
    "find_duplicate_enquiry_candidates": find_duplicate_enquiry_candidates,
}


# function for running the tools
# Generated with copilot, placeholder
def run_tool(
    tool_name: str,
    store: JsonStore,
    allowed_tool_names: set[str],
    **kwargs,
) -> str:
    """
    Run a tool by its name with the given store and arguments.

    Args:
        tool_name (str): The name of the tool to run.
        store (JsonStore): The JSON store instance.
        **kwargs: Additional keyword arguments to pass to the tool function.
        For example this could be the listing_id or building_id depending on the tool.

    Returns:
        str: The JSON string result of the tool execution or an error message.
    """

    if tool_name not in allowed_tool_names:
        return json.dumps({"error": f"Tool {tool_name} is not allowed."})

    if tool_name not in LOOKUP_DICT:
        return json.dumps({"error": f"Tool {tool_name} not found."})

    tool_func = LOOKUP_DICT[tool_name]

    # Every tool function have their own required arguments, which are passed via **kwargs

    try:
        result = tool_func(store, **kwargs)

        return result
    except TypeError as e:
        return json.dumps({"error": str(e)})
