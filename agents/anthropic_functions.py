import datetime
import json
import os
import re
import uuid

from anthropic import Anthropic

from core.store import NotFoundError
from core.tools import CHATBOT_SCHEMA_LIST, run_tool
from models.enquiry import Enquiry
from models.unit_enquiry import UnitEnquiry

SYSTEM_PROMPT = """
You extract information from rental unit enquiries.

Return only a JSON object with these fields:
name, email, phone, move_in_date, budget, message, listing_id, declined_fields.

Rules:
- Include all fields.
- Use null for missing information.
- budget must be an integer or null.
- move_in_date must use YYYY-MM-DD, or null when no unambiguous date is supplied.
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
"""

MODEL = "claude-haiku-5-5"
EXTRACTION_MAX_TOKENS = 1024

# For formal reasons, I created a redundant function.
def boot_anthropic():

    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    return client


def parse_model_json(text):
    """
    Parse extraction output as JSON, accepting plain JSON or a fenced JSON block.
    """

    try:
        return json.loads(text)
    except json.JSONDecodeError as initial_error:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if not match:
            raise ValueError(f"Model returned invalid JSON: {initial_error.msg}") from initial_error

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as fenced_error:
            raise ValueError(f"Model returned invalid JSON: {fenced_error.msg}") from fenced_error


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


def extract_enquiry_unit_enquiry(messages, client):
    """
    Extract a unit enquiry from the conversation messages using the Anthropic client.
    The function will be given the full message chain of the conversation up to this point.
    It is also given the Anthropic client to interact with the model for extraction.

    During the conversation, fields may be declined. The function will track which fields have been
    declined and return them along with the extracted enquiry. These declined fields are used
    for the agent triage.

    Args:
        messages (list): The conversation messages to send to the model.
        client: The Anthropic client used for interacting with the model.

    Returns:
        tuple: A tuple containing the extracted UnitEnquiry object and a set of declined fields.
    """

    # Send the messages to the model to get a response for the unit enquiry.
    response = client.messages.create(
        max_tokens=EXTRACTION_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
        model=MODEL,
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

    data = parse_model_json(text)

    # Now validate this JSON against the UnitEnquiry model to ensure it has the correct structure
    enquiry = UnitEnquiry.model_validate(data)

    # It is possible that the user declines to provide certain information. We need to check for that and track it
    # The system prompt accounts for this and has its dedicated field for it, so we can just extract it from the JSON
    declined = set(data.get("declined_fields") or [])

    # return it as a tuple
    return enquiry, declined


# Function used both in the rental chatbot and the agent triage system to run tools in a loop
def run_tool_loop(
    messages,
    client,
    data_store,
    system,
    on_event=None,
    tool_schemas=CHATBOT_SCHEMA_LIST,
    bound_tool_arguments=None,
    max_tokens: int = 1024,
):
    """
    Run the tool loop with the user, allowing the assistant to use tools to gather information.
    This function is used in both the rental chatbot and the agent triage. Send messages to Claude,
    execute any tools Claude requests, and repeat until Claude returns a normal text answer.

    Args:
        messages (list): The conversation messages between the user and the assistant.
        client: The Anthropic client used for interacting with the model.
        data_store (JsonStore): The data store containing listing information. (rental data).
        system (str): The system (instructions) prompt to guide the assistant's behavior.
        on_event (callable, optional): A callback function to capture events such as model calls and token usage.
        max_tokens (int): Maximum output tokens per model call. Truncated
            responses raise RuntimeError and are not accepted or retried.

    Returns:
        tuple: A tuple containing the assistant's response text (final answer) and the updated messages list.
        The updated message list is the conversation history including tool calls and result outputs.
    """

    # Validate the max_tokens parameter to ensure it is positive
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive.")

    # Define a counter to track the number of iterations in the tool loop
    while_iter = 0
    allowed_tool_names = {schema["name"] for schema in tool_schemas}
    bound_tool_arguments = bound_tool_arguments or {}

    # Start the tool loop, remember that there is a maximum of 6 iterations to avoid excessive costs
    while True:

        # To avoid costs, the loop only runs 6 times
        if while_iter >= 6:
            # If the loop has run 6 times, inform the user and exit to avoid excessive costs
            text = (
                "I'm having trouble completing that lookup right now. "
                "You can try another question or type 'done' to finish."
            )
            messages.append({"role": "assistant", "content": text})

            # Capture the response and return it along with the updated messages list
            return text, messages


        # At this stage we are still within the range of allowed iterations
        while_iter += 1

        # Prompt claude to enter the tool they want to use
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=tool_schemas,
            messages=messages,
        )

        # It is needed to capture/update the model and tokens used in this call
        # Capture and report the model call event if a callback is provided (EVENT)
        if on_event is not None:
            on_event(
                "model_call",
                model=MODEL,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
            )


        # At this stage the tool/response reason is given, which means;
        # The Agent has indicated it wants to use a tool to gather information.
        # OR The agent triage system has indicated it wants to use a tool to gather information.

        # It is possible to hit the max tokens
        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Model response truncated at configured max_tokens={max_tokens}. "
                "No complete response was accepted."
            )

        # This responses indicated the agent is finished and has provided a final answer.
        if response.stop_reason == "end_turn":

            # Final answer has been provided by the agent, append it to the messages and return it.
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return text, messages

        # This reponse indicates that the agent requires the use of a tool to gather information.
        elif response.stop_reason == "tool_use":

            # Capture the agent's indication to use a tool by appending it to the messages.
            messages.append({"role": "assistant", "content": response.content})

            # Initialize a list to store the results of tool usage
            results = []

            # Iterate through each block in the response content to identify tool usage requests
            for block in response.content:

                # Process each block in the response content to handle tool usage
                if block.type == "tool_use":
                    tool_arguments = {
                        **block.input,
                        **bound_tool_arguments.get(block.name, {}),
                    }

                    # Notify that a tool is being called, creating an EVENT
                    if on_event is not None:
                        on_event("tool_call", tool=block.name, args=tool_arguments)

                    # Run the tool with the provided input and capture the output
                    output = run_tool(
                        block.name,
                        data_store,
                        allowed_tool_names,
                        **tool_arguments,
                    )

                    # Attempt to parse the tool output as JSON to determine success
                    try:
                        output_data = json.loads(output)
                        tool_succeeded = not (
                            isinstance(output_data, dict) and "error" in output_data
                        )
                    except json.JSONDecodeError:
                        tool_succeeded = False

                    # Notify that a tool has returned a result. (EVENT)
                    if on_event is not None:
                        on_event(
                            "tool_result",
                            tool=block.name,
                            tool_succeeded=tool_succeeded,
                            tool_result=output,
                        )

                    # Append the tool result to the results list for later inclusion in the messages.
                    # This will be used for the agent triage
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

    usage = client.usage.retrieve()
    return usage
