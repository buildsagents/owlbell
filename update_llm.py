"""
Update the Retell LLM (llm_5ee8f9973b7c963225f12f7e8caf) with:
  - Comprehensive general_prompt (bilingual EN/ES, emotional awareness, tool usage)
  - Custom tool definitions for the 5 backend endpoints
  - Keep existing transfer_call and end_call tools

Usage:
    python update_llm.py

Env: INTEGRATION_RETELL_API_KEY, INTEGRATION_RETELL_AGENT_TOOLS_SECRET
"""

import os, sys, json, secrets
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

from retell import Retell

API_KEY = os.environ.get("INTEGRATION_RETELL_API_KEY")
if not API_KEY:
    print("FATAL: INTEGRATION_RETELL_API_KEY not set")
    sys.exit(1)

AGENT_TOOLS_SECRET = os.environ.get("INTEGRATION_RETELL_AGENT_TOOLS_SECRET")
if not AGENT_TOOLS_SECRET:
    AGENT_TOOLS_SECRET = "rt_" + secrets.token_hex(24)
    os.environ["INTEGRATION_RETELL_AGENT_TOOLS_SECRET"] = AGENT_TOOLS_SECRET
    print(f"Generated new AGENT_TOOLS_SECRET: {AGENT_TOOLS_SECRET}")
    # Write to .env
    with open(ENV_PATH, "a") as f:
        f.write(f"\nINTEGRATION_RETELL_AGENT_TOOLS_SECRET={AGENT_TOOLS_SECRET}\n")
    print(f"Written to {ENV_PATH}")

BASE_URL = "https://owlbell-api-production.up.railway.app"

client = Retell(api_key=API_KEY)

# ---------------------------------------------------------------------------
# General Prompt
# ---------------------------------------------------------------------------

GENERAL_PROMPT = """You are a warm, professional AI receptionist for {{business_name}}, a home-services company. Your job is to answer inbound calls, qualify leads, book appointments, take messages, and answer FAQs — all in a natural, conversational way.

## CRITICAL RULES

1. **AI Disclosure**: When you answer, say: "Hi, you've reached {{business_name}}! I'm an AI assistant, and this call may be recorded for quality and training purposes. How can I help you today?"
2. **Be warm and human**: Use natural conversational tone. Listen actively. Show empathy. Customers calling about home issues (leaks, broken AC, electrical problems) are often stressed — acknowledge their situation.
3. **Keep it concise**: Don't ramble. One or two sentences per turn is usually enough.
4. **Don't make things up**: Only answer from your knowledge base or available tools. If unsure, say "Let me transfer you to a team member who can help."
5. **Collect information naturally**: Don't interrogate. Ask one question at a time. Weave data collection into conversation.
6. **Confirm understanding**: Repeat back key details to verify.
7. **Always confirm next steps** before ending the call.

## BILINGUAL SUPPORT (ENGLISH / SPANISH)

- Detect the caller's language from their speech. Respond in the same language.
- If the caller speaks Spanish, respond in Spanish naturally.
- Key phrases in Spanish:
  - "Hi, you've reached..." = "Hola, has llamado a..."
  - "How can I help you?" = "¿Cómo puedo ayudarte?"
  - "Let me check that for you" = "Déjame verificar eso por ti"
  - "Thank you for calling" = "Gracias por llamar"
- For other languages, politely say you only speak English and Spanish, and offer to transfer.

## TOOLS AVAILABLE

You have the following tools. Use them at the right moment — do not simulate or pretend to perform actions. Actually call the tool.

1. **lookup_caller**: Check if we have a profile for this caller by their phone number. Call this at the START of the call after getting their phone number. If found, greet them by name.

2. **qualify_lead**: After you've determined the service needed, urgency, and have their contact info, call this tool to score and log the lead. Pass: caller_name, caller_phone, service, urgency (emergency/asap/flexible), address (if collected), notes (any relevant context).

3. **check_availability**: When a caller wants to book an appointment, call this tool with the requested date (YYYY-MM-DD). It returns available 30-minute slots. Present the options to the caller.

4. **book_appointment**: After the caller picks a time, call this tool with: caller_name, caller_phone, service, date, time, address (optional), notes (optional). Confirm the appointment details with the caller before finalizing.

5. **log_message**: If the caller doesn't want to book but wants to leave a message for the team, call this tool with: caller_name, caller_phone, message, email (optional).

## QUALIFICATION FLOW

When a caller expresses interest in a service:
1. Welcome them, ask how you can help.
2. Ask what service they need (HVAC, plumbing, electrical, roofing, general).
3. Get their name and phone number (use lookup_caller if they give a phone).
4. Ask about urgency: emergency (immediate danger/leak/break), ASAP (today/tomorrow), or flexible (anytime this week).
5. Ask for their address / location.
6. Call qualify_lead with what you have.
7. Offer to book an appointment or schedule a call back.

## APPOINTMENT BOOKING FLOW

1. Ask what date they're looking for.
2. Call check_availability to see open slots.
3. Present available times. If none available, suggest another date.
4. Once they choose, confirm: service, date, time, address, their name.
5. Call book_appointment to finalize.
6. Confirm the booking details back to them.

## MESSAGE TAKING FLOW

If the caller doesn't want to book and just wants to leave a message:
1. Ask for their name and phone number.
2. Ask for their message or what it's about.
3. Optionally ask for their email.
4. Call log_message.
5. Confirm the message was saved.

## FAQ HANDLING

- **Hours**: {{business_hours}}
- **Services**: {{services}}
- **Pricing**: {{pricing_info}}
- **Booking**: {{booking_link}}
- **Address**: {{business_address}}
- **Phone**: {{business_phone}}
- **Emergencies**: {{faq_emergency_contacts}}

## TRANSFERRING TO HUMAN

If the caller insists on speaking to a person, or asks something you can't handle:
- Use the transfer_to_human tool.
- Say: "Let me transfer you to one of our team members. Please hold."

## ENDING CALLS

Before ending, always:
1. Summarize what was accomplished.
2. Ask: "Is there anything else I can help you with?"
3. If no: "Thank you for calling {{business_name}}! Have a great day!"
4. Use the end_call tool.
"""

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def make_custom_tool(name, description, url, params_properties, required_params, execution_msg=None):
    tool = {
        "type": "custom",
        "name": name,
        "url": url,
        "method": "POST",
        "description": description,
        "headers": {
            "Authorization": f"Bearer {AGENT_TOOLS_SECRET}",
        },
        "parameters": {
            "type": "object",
            "properties": params_properties,
            "required": required_params,
        },
        "speak_during_execution": True,
        "speak_after_execution": True,
        "execution_message_description": execution_msg,
        "args_at_root": True,
    }
    return tool

TOOLS = [
    # Built-in tools
    {
        "type": "transfer_call",
        "name": "transfer_to_human",
        "description": "Transfer the call to a human team member when the customer needs personal assistance.",
        "transfer_destination": {
            "type": "predefined",
            "number": "{{transfer_number}}",
        },
        "transfer_option": {
            "type": "cold_transfer",
        },
        "speak_during_execution": True,
        "execution_message_description": "Say you're transferring them to a team member and ask them to hold.",
    },
    {
        "type": "end_call",
        "name": "end_call",
        "description": "End the call when the customer is satisfied and has no more questions.",
        "speak_during_execution": True,
        "execution_message_description": "Say a friendly goodbye and thank them for calling.",
    },
    # Custom tools
    make_custom_tool(
        name="lookup_caller",
        description="Look up a caller by their phone number. Call this at the start of the call to see if we know this person.",
        url=f"{BASE_URL}/api/v1/agent/tools/lookup-caller",
        params_properties={
            "phone_number": {
                "type": "string",
                "description": "Caller's phone number in E.164 format (e.g., +14155551234)",
            },
        },
        required_params=["phone_number"],
        execution_msg="Let me check our records for you.",
    ),
    make_custom_tool(
        name="qualify_lead",
        description="Score and log a lead after collecting service, urgency, and contact info from the caller.",
        url=f"{BASE_URL}/api/v1/agent/tools/qualify-lead",
        params_properties={
            "caller_name": {
                "type": "string",
                "description": "Caller's full name",
            },
            "caller_phone": {
                "type": "string",
                "description": "Caller's phone number in E.164 format",
            },
            "service": {
                "type": "string",
                "description": "Service needed (hvac, plumbing, electrical, roofing, general)",
            },
            "urgency": {
                "type": "string",
                "description": "Urgency level: emergency, asap, or flexible",
            },
            "address": {
                "type": "string",
                "description": "Caller's address / location (optional)",
            },
            "notes": {
                "type": "string",
                "description": "Any additional context about the call or request (optional)",
            },
        },
        required_params=["caller_name", "caller_phone", "service", "urgency"],
        execution_msg="Let me log that information for our team.",
    ),
    make_custom_tool(
        name="check_availability",
        description="Check available 30-minute appointment slots for a given date. Returns open time slots between 8 AM and 6 PM.",
        url=f"{BASE_URL}/api/v1/agent/tools/check-availability",
        params_properties={
            "date": {
                "type": "string",
                "description": "Date to check availability for in YYYY-MM-DD format",
            },
        },
        required_params=["date"],
        execution_msg="Let me check what times we have available.",
    ),
    make_custom_tool(
        name="book_appointment",
        description="Book an appointment for the caller after they've chosen a date and time. Use AFTER check_availability confirms the slot is open.",
        url=f"{BASE_URL}/api/v1/agent/tools/book-appointment",
        params_properties={
            "caller_name": {
                "type": "string",
                "description": "Caller's full name",
            },
            "caller_phone": {
                "type": "string",
                "description": "Caller's phone number in E.164 format",
            },
            "service": {
                "type": "string",
                "description": "Service needed (hvac, plumbing, electrical, roofing, general)",
            },
            "date": {
                "type": "string",
                "description": "Appointment date in YYYY-MM-DD format",
            },
            "time": {
                "type": "string",
                "description": "Appointment start time in HH:MM format (24-hour)",
            },
            "address": {
                "type": "string",
                "description": "Service address / location (optional)",
            },
            "notes": {
                "type": "string",
                "description": "Additional notes about the appointment (optional)",
            },
        },
        required_params=["caller_name", "caller_phone", "service", "date", "time"],
        execution_msg="Let me book that appointment for you.",
    ),
    make_custom_tool(
        name="log_message",
        description="Save a message from a caller who doesn't want to book but wants to leave information for the team.",
        url=f"{BASE_URL}/api/v1/agent/tools/log-message",
        params_properties={
            "caller_name": {
                "type": "string",
                "description": "Caller's full name",
            },
            "caller_phone": {
                "type": "string",
                "description": "Caller's phone number in E.164 format",
            },
            "message": {
                "type": "string",
                "description": "The message the caller wants to leave",
            },
            "email": {
                "type": "string",
                "description": "Caller's email address (optional)",
            },
        },
        required_params=["caller_name", "caller_phone", "message"],
        execution_msg="Let me save that message for our team.",
    ),
]

# ---------------------------------------------------------------------------
# Update LLM
# ---------------------------------------------------------------------------

print("Updating LLM llm_5ee8f9973b7c963225f12f7e8caf...")
print(f"Tools to register: {[t['name'] for t in TOOLS]}")

response = client.llm.update(
    llm_id="llm_5ee8f9973b7c963225f12f7e8caf",
    general_prompt=GENERAL_PROMPT,
    general_tools=TOOLS,
    model_temperature=0.4,
)

print(f"  Version: {response.version}")
print(f"  Is published: {response.is_published}")
print(f"  Tools: {len(response.general_tools or [])}")
print()
print("=== DONE ===")
print("LLM updated successfully.")
print()
print("Next steps:")
print("  1. Deploy the updated backend to Railway (includes agent_tools router)")
print("  2. Verify the webhook reaches the new agent_tools endpoints")
print("  3. Make a test call to verify the full flow")
