# The tools file is similar to the controllers found in Java

import json

from core.store import JsonStore, NotFoundError


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
            "listing_id": {"type": "string", "description": "The ID of the listing to retrieve."}
        },
    }
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
            "building_id": {"type": "string", "description": "The ID of the building to retrieve."}
        },
    }
}

# Schema list
SCHEMA_LIST = [GET_LISTING_SCHEMA, GET_BUILDING_SCHEMA]

# Lookup dict
LOOKUP_DICT = {
    "get_listing": get_listing,
    "get_building": get_building
}


# function for running the tools
# Generated with copilot, placeholder
def run_tool(tool_name: str, store: JsonStore, **kwargs) -> str:
    """
    Run a tool by its name with the given store and arguments.

    Args:
        tool_name (str): The name of the tool to run.
        store (JsonStore): The JSON store instance.
        **kwargs: Additional keyword arguments to pass to the tool function.

    Returns:
        str: The JSON string result of the tool execution or an error message.
    """

    if tool_name not in LOOKUP_DICT:
        return json.dumps({"error": f"Tool {tool_name} not found."})
    
    tool_func = LOOKUP_DICT[tool_name]

    return tool_func(store, **kwargs)
