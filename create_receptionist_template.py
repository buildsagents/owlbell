"""
Retell Inbound Receptionist Template — Home Services
====================================================
Creates: (a) Retell LLM, (b) Knowledge Base, (c) Agent
Saves a versioned JSON template for per-client cloning.

Usage:
    python create_receptionist_template.py

Env: INTEGRATION_RETELL_API_KEY must be set in .env or environment.
"""

import json, os, sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from retell import Retell

API_KEY = os.environ.get("INTEGRATION_RETELL_API_KEY")
if not API_KEY:
    print("FATAL: INTEGRATION_RETELL_API_KEY not set")
    sys.exit(1)

client = Retell(api_key=API_KEY)

# ---------------------------------------------------------------------------
# Template variables — override these per client
# ---------------------------------------------------------------------------
TEMPLATE = {
    "template_name": "owlbell-inbound-receptionist",
    "template_version": "1.0.0",
    "created": datetime.utcnow().isoformat() + "Z",
    "description": "Inbound receptionist for home-services businesses (HVAC, plumbing, roofing, electrical, etc.)",
    "variables": {
        "business_name":        {"type": "string", "default": "", "description": "Business name"},
        "business_hours":       {"type": "string", "default": "Monday to Friday, 8 AM to 6 PM", "description": "Hours of operation"},
        "services":             {"type": "string", "default": "HVAC repair, plumbing, electrical", "description": "Comma-separated list of services"},
        "pricing_info":         {"type": "string", "default": "We offer free estimates. Pricing varies by job.", "description": "Pricing description"},
        "booking_link":         {"type": "string", "default": "", "description": "Booking URL (Calendly, Cal.com, etc.)"},
        "business_address":     {"type": "string", "default": "", "description": "Physical address"},
        "business_phone":       {"type": "string", "default": "", "description": "Business phone number"},
        "transfer_number":      {"type": "string", "default": "", "description": "Number to transfer calls to"},
        "faq_emergency_contacts": {"type": "string", "default": "For emergencies, call 911.", "description": "Emergency contact instructions"},
    },
    "llm_id": None,
    "knowledge_base_id": None,
    "agent_id": None,
}

# ---------------------------------------------------------------------------
# 1. Create Knowledge Base
# ---------------------------------------------------------------------------

KB_TEXTS = [
    {
        "title": "Business Hours",
        "text": (
            "Our business hours are {{business_hours}}. "
            "We are closed on major holidays. Emergency service may be available — please call to check."
        ),
    },
    {
        "title": "Services Offered",
        "text": (
            "We offer the following services: {{services}}. "
            "Each service includes a free estimate. Contact us for detailed pricing."
        ),
    },
    {
        "title": "Pricing and Estimates",
        "text": (
            "{{pricing_info}} We accept credit cards, cash, and financing options. "
            "Ask about our seasonal specials!"
        ),
    },
    {
        "title": "Scheduling and Booking",
        "text": (
            "You can book an appointment online at {{booking_link}} "
            "or call us at {{business_phone}}. We typically schedule within 24-48 hours."
        ),
    },
    {
        "title": "Service Area",
        "text": (
            "We serve the local area around {{business_address}}. "
            "Please call to confirm if we cover your location."
        ),
    },
    {
        "title": "Emergency Service",
        "text": (
            "{{faq_emergency_contacts}} For urgent home service needs during business hours, "
            "we will do our best to accommodate same-day service."
        ),
    },
    {
        "title": "Cancellation Policy",
        "text": (
            "We require 24-hour notice for cancellations. "
            "Late cancellations may be subject to a fee."
        ),
    },
]

print("--- Creating Knowledge Base ---")
kb_response = client.knowledge_base.create(
    knowledge_base_name="Owlbell Home Services FAQ",
    knowledge_base_texts=KB_TEXTS,
)
kb_id = kb_response.knowledge_base_id
print(f"Knowledge Base ID: {kb_id} (status: {kb_response.status})")
TEMPLATE["knowledge_base_id"] = kb_id

# ---------------------------------------------------------------------------
# 2. Create Retell LLM
# ---------------------------------------------------------------------------

GENERAL_PROMPT = """You are a friendly, efficient AI receptionist for {{business_name}}. You answer inbound calls from customers seeking home services.

## CRITICAL RULES
1. **AI Disclosure**: At the very start of the call, clearly state: "Hi, you've reached {{business_name}}! I'm an AI assistant, and this call may be recorded for quality and training purposes. How can I help you today?"
2. **Stay in scope**: Only answer questions about {{business_name}}'s services, pricing, scheduling, and policies. If asked about anything outside your knowledge, say "I'm not sure about that — let me transfer you to a team member who can help."
3. **Be helpful & efficient**: Keep responses concise and professional. Don't be overly chatty.
4. **Collect information**: When a customer wants to book or get a quote, collect: service needed, their name, phone number, address, and preferred time.

## QUALIFICATION FLOW
When a customer expresses interest in a service:
1. Ask what service they need (from: {{services}})
2. Ask for their name and phone number
3. Ask for their address / location
4. Ask about urgency (emergency, ASAP, or flexible)
5. Offer to book an appointment or transfer to a team member

## HANDLING FAQs
- **Hours**: {{business_hours}}
- **Services**: {{services}}
- **Pricing**: {{pricing_info}}
- **Booking**: {{booking_link}}
- **Address**: {{business_address}}
- **Phone**: {{business_phone}}
- **Emergencies**: {{faq_emergency_contacts}}

## TRANSFERRING
If the customer needs to speak with a human:
- Use the transfer call tool to send them to {{transfer_number}}
- Say: "Let me transfer you to one of our team members who can help with that. Please hold."

## ENDING CALLS
Always confirm next steps before ending. Say something like:
"Great, I've scheduled your appointment for [time]. Is there anything else I can help you with?"
If nothing else: "Thank you for calling {{business_name}}! Have a great day!"
"""

print("\n--- Creating Retell LLM ---")
llm_response = client.llm.create(
    general_prompt=GENERAL_PROMPT,
    general_tools=[
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
    ],
    start_speaker="agent",
    begin_message="Hi, you've reached {{business_name}}! I'm an AI assistant, and this call may be recorded. How can I help you today?",
    model="gpt-4.1-mini",
    model_temperature=0.3,
)
llm_id = llm_response.llm_id
print(f"LLM ID: {llm_id} (version: {llm_response.version})")
TEMPLATE["llm_id"] = llm_id

# ---------------------------------------------------------------------------
# 3. Update LLM with knowledge base
# ---------------------------------------------------------------------------
print("\n--- Attaching Knowledge Base to LLM ---")
client.llm.update(
    llm_id=llm_id,
    knowledge_base_ids=[kb_id],
)
print("Knowledge base attached.")

# ---------------------------------------------------------------------------
# 4. Create Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "Owlbell Receptionist"
VOICE_ID = "retell-Willa"  # Platform voice — good quality, low cost

print(f"\n--- Creating Agent (voice: {VOICE_ID}) ---")
agent_response = client.agent.create(
    agent_name=AGENT_NAME,
    response_engine={
        "type": "retell-llm",
        "llm_id": llm_id,
    },
    voice_id=VOICE_ID,
    webhook_url=os.environ.get("RETELL_WEBHOOK_URL", "https://owlbell-api-production.up.railway.app/api/v1/webhooks/retell"),
    webhook_events=["call_started", "call_ended", "call_analyzed"],
    language="en-US",
    enable_backchannel=True,
    interruption_sensitivity=0.7,
    responsiveness=0.8,
    end_call_after_silence_ms=30000,
    max_call_duration_ms=1800000,  # 30 min
)
agent_id = agent_response.agent_id
print(f"Agent ID: {agent_id} (version: {agent_response.version})")
TEMPLATE["agent_id"] = agent_id

# ---------------------------------------------------------------------------
# 5. Save Template
# ---------------------------------------------------------------------------

template_path = Path(__file__).parent / "receptionist-template.json"
with open(template_path, "w") as f:
    json.dump(TEMPLATE, f, indent=2, default=str)
print(f"\nTemplate saved: {template_path}")

print("\n=== DONE ===")
print(f"  LLM:           {llm_id}")
print(f"  Knowledge Base: {kb_id}")
print(f"  Agent:          {agent_id}")
print()
print("To clone for a new client:")
print("  1. Copy receptionist-template.json")
print("  2. Fill in the 'variables' section")
print("  3. Create a new LLM version with client-specific prompt")
print("  4. Update the agent to point to the new LLM version")
