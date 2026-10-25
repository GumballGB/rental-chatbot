import dotenv

import agents.anthropic_functions as af
from core.store import JsonStore

dotenv.load_dotenv()

if __name__ == "__main__":
    client = af.boot_anthropic()
    data_store = JsonStore()
    enquiry, declined_fields = af.run_rental_chat(client, data_store)

    print(enquiry.model_dump())
    print({"declined_fields": sorted(declined_fields)})
