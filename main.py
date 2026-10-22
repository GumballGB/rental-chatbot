import os
from anthropic import Anthropic

client = Anthropic(
    # This is straight from the documentation
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

def get_response(prompt):
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


if __name__ == "__main__":

    print("Enter your prompt")

    user_message = input()
    print(get_response(user_message))
