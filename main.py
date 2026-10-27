import dotenv

from agents.anthropic_functions import boot_anthropic
from agents.rental_chatbot import run_rental_chat
from core.store import JsonStore

dotenv.load_dotenv()

if __name__ == "__main__":
    client = boot_anthropic()
    data_store = JsonStore()
    enquiry, declined_fields = run_rental_chat(client, data_store)

    print(enquiry.model_dump())
    print({"declined_fields": sorted(declined_fields)})
