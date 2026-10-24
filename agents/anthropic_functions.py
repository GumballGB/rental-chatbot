import datetime
import json
import os
import uuid

from anthropic import Anthropic

from core import store
from models.enquiry import Enquiry
from models.unit_enquiry import UnitEnquiry

SYSTEM_PROMPT = """
You extract information from rental unit enquiries.

Return only a JSON object with these fields:
name, email, phone, move_in_date, budget, message, listing, declined_fields.

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
    declined = set(data.get("declined_fields" or []))

    # return it as a tuple
    return enquiry, declined



def get_response_unit_enquiry(client):

    # Get the user's answer
    print("Assistant: Hello! I am a rental assistant, how can I help you today?")
    answer = input("You: ")

    # Keep track of the conversation history
    messages = [
        {"role": "user", "content": answer}
    ]

    # Define the questions we will ask for each field
    questions = {
        "name": "What is your name?",
        "email": "What is your email address?",
        "phone": "What is your phone number?",
        "move_in_date": "When would you like to move in?",
        "budget": "What is your monthly budget?",
        "message": "What are you looking for in a rental unit?",
        "listing_id": "What listing are you interested in?"
    }

    while(True):

        # extract the message from the response, declined probably starts empty, but we will check for it anyway
        enquiry, declined = get_single_response_unit_enquiry(messages, client)

        data = enquiry.model_dump()  # Convert the Pydantic model to a dictionary

        # Check for missing fields that is not declined
        missing_fields = []

        for field, value in data.items():
            if value is None and field not in declined:
                missing_fields.append(field)
        
        # if nothing is missing, finish and break the loop, otherwise ask for the missing fields
        if not missing_fields:

            # The unit enquiry is complete, but we still need to populate 
            # some additional fields like enquiry_id, received_date, and budget_currency.
            # Todo: probably make a helper function to avoid code monster

            data["enquiry_id"] = f"ENQ-{uuid.uuid4()}"
            data["received_date"] = str(datetime.date.today())
            data["listing_id"] = data.get("listing_id")
            data["budget_currency"] = None

            # this will not work for now
            data["listing_id"] = data.get("listing_id")
            listing_id = data["listing_id"]
            listing = store.get_listing(listing_id)
            building = store.get_building(listing.building_id)
            data["budget_currency"] = store.get_listing(listing_id).currency


            enquiry = Enquiry(**data) # created enquiries have uuid IDs instead

            return enquiry

        # Prepare to ask for the missing fields, this is not AI
        field = missing_fields[0]
        question = questions[field]

        # Ask the user for the missing field
        print(f"Assistant: {question}")

        # Save the assistant's question
        messages.append({
            "role": "assistant",
            "content": question
        })

        # Get the user's answer
        answer = input("You: ")

        # Save the user's answer
        messages.append({
            "role": "user",
            "content": answer
        })

        # At this stage, the AI will process the next message with some context


def get_usage(client):

    if not verify_client(client):
        raise TypeError("Anthropic AI not configured.")

    usage = client.usage.retrieve()
    return usage