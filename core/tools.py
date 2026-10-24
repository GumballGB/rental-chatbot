# The tools file is similar to the controllers found in Java
# Generated with copilot

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
        "required": ["listing_id"]
    }
}