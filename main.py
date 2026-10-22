import agents.anthropic_functions as af
from models.unit_enquiry import UnitEnquiry
import json


if __name__ == "__main__":

    client = af.boot_anthropic()

    print("Enter your prompt")
    user_message = input()

    response = af.get_response_classify_unit_enquiry(user_message, client)

    clean= UnitEnquiry.model_validate_json(response)  # Validate that the response can be parsed into a UnitEnquiry model

    print(clean)
