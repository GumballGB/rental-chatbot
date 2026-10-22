import agents.anthropic_functions as af
from models.unit_enquiry import UnitEnquiry
import json


if __name__ == "__main__":

    client = af.boot_anthropic()


    enquiry = af.get_response_unit_enquiry(client)

    # Convert the enquiry to a dictionary
    enquiry_dict = enquiry.model_dump()

    print(enquiry_dict)
