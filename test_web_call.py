"""Create a test web call and show the access token."""
import os
from dotenv import load_dotenv
load_dotenv()

from retell import Retell

client = Retell(api_key=os.environ["INTEGRATION_RETELL_API_KEY"])

# Use the agent we just created
agent_id = "agent_233aac32d03d073ad7774a5ca2"

print("Creating web call...")
web_call = client.call.create_web_call(
    agent_id=agent_id,
    retell_llm_dynamic_variables={
        "business_name": "Test Company",
        "business_hours": "Monday to Friday, 8 AM to 6 PM",
        "services": "HVAC repair, plumbing, electrical",
        "pricing_info": "Free estimates. Pricing varies by job.",
        "booking_link": "https://calendly.com/test-company",
        "business_address": "123 Main St, Austin, TX",
        "business_phone": "+15125551234",
        "transfer_number": "+15125559876",
        "faq_emergency_contacts": "For emergencies, call 911.",
    },
)

print(f"Call ID:       {web_call.call_id}")
print(f"Access Token:  {web_call.access_token}")
print()
print("=== TEST IN BROWSER ===")
print(f"Open this URL to speak with the agent:")
print(f"  https://www.retellai.com/web-call/{web_call.access_token}")
print()
print("After you finish the call, I can fetch the transcript.")
