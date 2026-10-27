# Rental Chatbot Agent
# This agent handles the interaction with users for rental enquiries, gathers information,
# and converts it into structured Enquiry objects using a two-phase approach: natural language loop and extraction.

from agents.anthropic_functions import (
    TOOL_SYSTEM_PROMPT,
    create_enquiry,
    extract_enquiry_unit_enquiry,
    run_tool_loop,
)


# The function to run the CHAT BOT for rental enquiries, generates an Enquiry object.
def run_rental_chat(client, data_store):
    """
    Run the rental chat with the user, gather information, and create an Enquiry object.
    There are two major phases in this function: the natural language loop phase,
    where the user interacts with the assistant, and the extraction phase,
    where the gathered information is converted into an Enquiry object.

    Args:
        client: The Anthropic client used for interacting with the model.
        data_store (JsonStore): The data store containing listing information.

    Returns:
        tuple: A tuple containing the created Enquiry object and a set of declined fields.
    """

    # Create initial fields for the conversation messages
    tool_messages = []
    plain_messages = [] # Will store the conversation messages for the plain loop (user-assistant)

    print("Assistant: Hello! Ask me about a rental. Type 'done' when finished.")

    # -*-*- NATURAL LANGUAGE LOOP PHASE -*-*- #

    while True:

        user_message = input("You: ").strip()

        # If the user types 'done', we exit the loop
        if user_message.lower() == "done":
            break

        # Skip empty user messages
        if not user_message:
            continue

        # Record the user's turn in both the tool and plain message lists
        user_turn = {"role": "user", "content": user_message}
        tool_messages.append(user_turn)
        plain_messages.append(user_turn.copy())

        # Prepare the tool loop with the current conversation messages
        # Note that tool_messages is mutated but returned as well, so we capture the updated list.
        assistant_message, tool_messages = run_tool_loop(
            tool_messages,
            client,
            data_store,
            system=TOOL_SYSTEM_PROMPT, # The prompt is what makes this a rental chatbot experience.
        )

        # Capture and display the assistant's last response for the user.
        print(f"Assistant: {assistant_message}")
        plain_messages.append({"role": "assistant", "content": assistant_message})

    # At this point, the conversation has ended.

    # Another claude call will be made, but if the conversation is empty, we just raise an error.
    if not plain_messages:
        raise RuntimeError("Cannot create an enquiry from an empty conversation.")

    # -*-*- EXTRACTION PHASE -*-*- #
    # CONVERSION TO ENQUIRY OBJECT

    # Build the extraction messages for the final Claude call to extract the rental enquiry.
    extraction_messages = [
        *plain_messages,
        {
            "role": "user",
            "content": "Extract the rental enquiry from this conversation.",
        },
    ]

    # Call the function to get the unit enquiry and any declined fields from the extraction messages.
    unit_enquiry, declined_fields = extract_enquiry_unit_enquiry(
        extraction_messages,
        client,
    )

    # Finally, create the enquiry object from the extracted unit enquiry.
    enquiry = create_enquiry(unit_enquiry.model_dump(), data_store)

    return enquiry, declined_fields
