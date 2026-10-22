import agents.anthropic_functions as af


if __name__ == "__main__":

    client = af.boot_anthropic()

    print("Enter your prompt")
    user_message = input()

    response = af.get_response(user_message, client)

    print(response)
