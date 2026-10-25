import datetime
import json
import os
import uuid

from anthropic import Anthropic

from models.enquiry import Enquiry
from models.unit_enquiry import UnitEnquiry
from core.store import NotFoundError
from core.tools import run_tool, SCHEMA_LIST

SYSTEM_PROMPT = """
You extract information from rental unit enquiries.

Return only a JSON object with these fields:
name, email, phone, move_in_date, budget, message, listing_id, declined_fields.

Rules:
- Include all fields.
- Use null for missing information.
- budget must be an integer or null.
- declined_fields must be an array of field names that
  the user has explicitly refused to provide.
- Try to find the desired listing name or building name of the enquiry
- Extract information from the entire conversation.
- Preserve previously supplied information.
- If a user corrects a value, use the latest value.
- Never invent information.
- Never treat an unanswered question as a refusal.
- Return only valid JSON.
- Do not put any extra text outside the JSON object, such as fences.
"""

TOOL_SYSTEM_PROMPT = """
You are a tool-using assistant. You are knowledgeable about listings and buildings,
use the tools to look things up, and never invent details. You have a set of tools to
use to extract information about listings, buildings and locations.
Nevertheless, your goal is gather information about the enquiry from the user.
Ask the user to get the necessary information about the rental enquiry, such as
listing name, building name, and location. You only have 6 attempts to gather this information,
so you may ask multiple questions to gather all the necessary details.
The user may decline some information, and you should track which fields are declined.

Additionally, this is all fictionial data, the listings and buildings do not correspond to real-world entities.
The data may already hint at this, but assume that the user is already aware of this, so pretend it is "real".
"""

# For formal reasons, I created a redundant function.
def boot_anthropic():

    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    return client


def verify_client(client):

    if not isinstance(client, Anthropic):
        print("Client is not an instance of Anthropic.")
        return False
    return True


def get_single_response_unit_enquiry(messages, client):

    if not verify_client(client):
        raise TypeError("Anthropic AI not configured.")

    response = client.messages.create(
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
        model="claude-haiku-5-5",
    )

    # We need to convert the list of blocks into a single string, so we can parse it as JSON later
    # We expect a completed response before parsing JSON
    if response.stop_reason != "end_turn":
        raise RuntimeError(
            f"Extraction did not finish: {response.stop_reason}"
        )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    # At this stage our text is still a string, we need to convert it into a JSON

    data = json.loads(text)

    # Now validate this JSON against the UnitEnquiry model to ensure it has the correct structure
    enquiry = UnitEnquiry.model_validate(data)

    # It is possible that the user declines to provide certain information. We need to check for that and track it
    # The system prompt accounts for this and has its dedicated field for it, so we can just extract it from the JSON
    declined = set(data.get("declined_fields") or [])

    # return it as a tuple
    return enquiry, declined


# Helper function to create an Enquiry object from the extracted data and the data store
def create_enquiry(data, data_store):
    """
    Create an Enquiry object from the extracted data and the data store.

    Args:
        data (dict): The extracted data from the conversation.
        data_store (JsonStore): The data store containing listing information.

    Returns:
        Enquiry: The created Enquiry object.
    """

    enquiry_data = {
        **data,
        "enquiry_id": f"ENQ-{uuid.uuid4()}",
        "received_date": datetime.date.today().isoformat(),
        "budget_currency": None,
    }

    listing_id = enquiry_data.get("listing_id")
    if listing_id is not None:
        try:
            enquiry_data["budget_currency"] = data_store.get_listing(listing_id).currency
        except NotFoundError:
            enquiry_data["listing_id"] = None

    return Enquiry(**enquiry_data)


def run_rental_chat(client, data_store):
    """
    Run the rental chat with the user, gather information, and create an Enquiry object.

    Args:
        client: The Anthropic client used for interacting with the model.
        data_store (JsonStore): The data store containing listing information.

    Returns:
        tuple: A tuple containing the created Enquiry object and a set of declined fields.
    """

    tool_messages = []
    plain_messages = []

    print("Assistant: Hello! Ask me about a rental. Type 'done' when finished.")

    while True:
        user_message = input("You: ").strip()

        if user_message.lower() == "done":
            break

        if not user_message:
            continue

        user_turn = {"role": "user", "content": user_message}
        tool_messages.append(user_turn)
        plain_messages.append(user_turn.copy())

        assistant_message, tool_messages = run_tool_loop(
            tool_messages,
            client,
            data_store,
        )
        print(f"Assistant: {assistant_message}")
        plain_messages.append({"role": "assistant", "content": assistant_message})

    if not plain_messages:
        raise RuntimeError("Cannot create an enquiry from an empty conversation.")

    extraction_messages = [
        *plain_messages,
        {
            "role": "user",
            "content": "Extract the rental enquiry from this conversation.",
        },
    ]
    unit_enquiry, declined_fields = get_single_response_unit_enquiry(
        extraction_messages,
        client,
    )
    enquiry = create_enquiry(unit_enquiry.model_dump(), data_store)

    return enquiry, declined_fields


# Functions to now use the tools for Claude
def run_tool_loop(messages, client, data_store):
    """
    Run the tool loop with the user, allowing the assistant to use tools to gather information.

    Args:
        messages (list): The conversation messages between the user and the assistant.
        client: The Anthropic client used for interacting with the model.
        data_store (JsonStore): The data store containing listing information.

    Returns:
        tuple: A tuple containing the assistant's response text and the updated messages list.
    """

    while_iter = 0

    while True:

        # To avoid costs, the chatbot will only run for 6 times
        if while_iter >= 6:
            text = (
                "I'm having trouble completing that lookup right now. "
                "You can try another question or type 'done' to finish."
            )
            messages.append({"role": "assistant", "content": text})
            return text, messages


        # At this stage we are still within the range of allowed iterations
        while_iter += 1

        # Prompt claude to enter the tool they want to use
        response = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=1024,
            system=TOOL_SYSTEM_PROMPT,
            tools=SCHEMA_LIST,
            messages=messages,
        )


        # At this stage the tool reason is dropped

        if response.stop_reason == "end_turn":

            messages.append({
                "role": "assistant",
                "content": response.content
            })

            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return text, messages

        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = run_tool(block.name, data_store, **block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})

            messages.append({"role": "user", "content": results})

        else:
            raise RuntimeError(f"Unexpected tool response: {response.stop_reason}")



def get_usage(client):
    """
    Retrieve the usage information for the Anthropic client.

    Args:
        client: The Anthropic client used for interacting with the model.

    Returns:
        dict: The usage information retrieved from the client.
    """

    if not verify_client(client):
        raise TypeError("Anthropic AI not configured.")

    usage = client.usage.retrieve()
    return usage
