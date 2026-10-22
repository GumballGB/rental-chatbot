import os
import anthropic as Anthropic

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


'''
This function has to verify that a client exists in the first place
'''
def get_response(prompt, client):

    if not verify_client(client):
        raise TypeError("Anthropic AI not configured.")

    message = client.messages.create(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="claude-haiku-5-5",
    )

    for block in message.content:
        if block.type == "text":
            return block.text


def get_usage(client):

    if not verify_client(client):
        raise TypeError("Anthropic AI not configured.")

    usage = client.usage.retrieve()
    return usage