"""
Generate the n8n auto-provisioning workflow JSON.

Usage:
    python n8n/generate-workflow.py

Output:
    n8n/retell-provisioning.json  — importable into n8n
"""

import json, uuid
from datetime import datetime

def uid() -> str:
    return str(uuid.uuid4())

def node(name: str, type_name: str, params: dict, pos: list[int], version=1, extras=None):
    n = {
        "id": uid(),
        "name": name,
        "type": f"n8n-nodes-base.{type_name}",
        "typeVersion": version,
        "position": pos,
        "parameters": params,
    }
    if extras:
        n.update(extras)
    return n

# ---------------------------------------------------------------------------
# Node definitions
# ---------------------------------------------------------------------------
W = 250  # horizontal spacing
H = 220  # vertical spacing
X0 = 0
Y0 = 0

nodes = []
edges = []

def add(n):
    nodes.append(n)
    return n["name"]

def link(from_name, to_name, output_index=0, input_index=0):
    edges.append({
        "from": from_name,
        "to": to_name,
        "fromOutputIndex": output_index,
        "toInputIndex": input_index,
    })

# ---- 1. Webhook trigger ----
add(node(
    "Stripe Webhook", "webhook",
    {
        "path": "stripe-checkout-completed",
        "responseMode": "responseNode",
        "options": {},
        "webhookId": uid(),
        "httpMethod": "POST",
        "rawBody": True,
    },
    [X0, Y0],
))

# ---- 1b. Verify Stripe Webhook Signature (optional but recommended) ----
# NOTE: Uncomment this node to verify Stripe signatures before processing.
# You'll need to configure the STRIPE_WEBHOOK_SECRET environment variable in n8n.
#
# add(node(
#     "Verify Stripe Signature", "code",
#     {
#         "jsCode": """// Verify Stripe webhook signature
# // n8n stores the raw body in $input.first().json.__raw_body__ when rawBody is true
# // For production, use n8n's built-in Stripe node instead of raw webhook
#
# const stripeSecret = process.env.STRIPE_WEBHOOK_SECRET;
# if (!stripeSecret) {
#   console.warn('STRIPE_WEBHOOK_SECRET not set - skipping signature verification');
#   return $input.first().json;
# }
#
# // Stripe signature verification requires the Stripe SDK
# // const stripe = require('stripe')(stripeSecret);
# // const event = stripe.webhooks.constructEvent(rawBody, signature, stripeSecret);
# // return event;
#
# // For now, just pass through with a warning
# console.warn('Stripe webhook signature verification not implemented');
# return $input.first().json;
# """
#     },
#     [X0 + W, Y0],
# ))
# (adjust the connection below to go through this node if uncommented)

# ---- 2. Parse metadata ----
add(node(
    "Parse & Validate Intake", "code",
    {
        "jsCode": """// Extract and validate Stripe checkout metadata
const session = $input.first().json;
const meta = session.data?.object?.metadata || {};

// Required fields
const required = ['business_name', 'email', 'phone'];
for (const field of required) {
  if (!meta[field]) throw new Error(`Missing required metadata: ${field}`);
}

// Build the general_prompt template with their intake
const businessName = meta.business_name;
const businessHours = meta.business_hours || 'Monday to Friday, 8 AM to 6 PM';
const services = meta.services || 'HVAC repair, plumbing, electrical, roofing, general';
const pricingInfo = meta.pricing_info || 'We offer free estimates. Pricing varies by job.';
const bookingLink = meta.booking_link || '';
const businessAddress = meta.business_address || '';
const businessPhone = meta.phone;
const transferNumber = meta.transfer_number || meta.phone;
const emergencyContacts = meta.faq_emergency_contacts || 'For emergencies, call 911.';

const generalPrompt = `You are a warm, professional AI receptionist for ${businessName}, a home-services company. Your job is to answer inbound calls, qualify leads, book appointments, take messages, and answer FAQs — all in a natural, conversational way.

## CRITICAL RULES
1. **AI Disclosure**: When you answer, say: "Hi, you've reached ${businessName}! I'm an AI assistant, and this call may be recorded for quality and training purposes. How can I help you today?"
2. **Be warm and human**: Use natural conversational tone. Listen actively. Show empathy.
3. **Keep it concise**: Don't ramble. One or two sentences per turn is usually enough.
4. **Don't make things up**: Only answer from your knowledge base or available tools.
5. **Collect information naturally**: Don't interrogate. Ask one question at a time.
6. **Confirm understanding**: Repeat back key details to verify.
7. **Always confirm next steps** before ending the call.

## BILINGUAL SUPPORT (ENGLISH / SPANISH)
- Detect the caller's language from their speech. Respond in the same language.
- If the caller speaks Spanish, respond in Spanish naturally.
- Key phrases in Spanish: "Hola, has llamado a ${businessName}!", "¿Cómo puedo ayudarte?", "Déjame verificar eso por ti", "Gracias por llamar"
- For other languages, politely say you only speak English and Spanish, and offer to transfer.

## TOOLS AVAILABLE
1. **lookup_caller**: Check if we have a profile for this caller. Call at START after getting phone number.
2. **qualify_lead**: After collecting service, urgency, and contact info, score and log the lead.
3. **check_availability**: When caller wants to book, check open slots for a date.
4. **book_appointment**: After caller picks a time, finalize the booking.
5. **log_message**: If caller doesn't want to book but wants to leave a message.

## FAQ
- Hours: ${businessHours}
- Services: ${services}
- Pricing: ${pricingInfo}
- Booking: ${bookingLink}
- Address: ${businessAddress}
- Phone: ${businessPhone}
- Emergencies: ${emergencyContacts}

## HANDLING FAQs
- **Hours**: ${businessHours}
- **Services**: ${services}
- **Pricing**: ${pricingInfo}
- **Booking**: ${bookingLink}
- **Address**: ${businessAddress}
- **Phone**: ${businessPhone}
- **Emergencies**: ${emergencyContacts}

## TRANSFERRING TO HUMAN
If the caller insists on speaking to a person, or asks something you can't handle:
- Use the transfer_to_human tool.
- Say: "Let me transfer you to one of our team members. Please hold."

## ENDING CALLS
Before ending, always:
1. Summarize what was accomplished.
2. Ask: "Is there anything else I can help you with?"
3. If no: "Thank you for calling ${businessName}! Have a great day!"
4. Use the end_call tool.`;

const knowledgeBaseTexts = [
  {
    title: 'Business Hours',
    text: `Our business hours are ${businessHours}. We are closed on major holidays. Emergency service may be available — please call to check.`
  },
  {
    title: 'Services Offered',
    text: `We offer the following services: ${services}. Each service includes a free estimate. Contact us for detailed pricing.`
  },
  {
    title: 'Pricing and Estimates',
    text: `${pricingInfo} We accept credit cards, cash, and financing options. Ask about our seasonal specials!`
  },
  {
    title: 'Scheduling and Booking',
    text: `You can book an appointment online at ${bookingLink} or call us at ${businessPhone}. We typically schedule within 24-48 hours.`
  },
  {
    title: 'Service Area',
    text: `We serve the local area around ${businessAddress}. Please call to confirm if we cover your location.`
  },
  {
    title: 'Emergency Service',
    text: `${emergencyContacts} For urgent home service needs during business hours, we will do our best to accommodate same-day service.`
  },
  {
    title: 'Cancellation Policy',
    text: 'We require 24-hour notice for cancellations. Late cancellations may be subject to a fee.'
  },
];

return {
  session_id: session.data?.object?.id,
  customer_email: meta.email,
  business_name: businessName,
  business_phone: businessPhone,
  services: services,
  area_code: meta.area_code || '555',
  general_prompt: generalPrompt,
  knowledge_base_texts: JSON.stringify(knowledgeBaseTexts),
  kb_name: `${businessName} FAQ`,
  agent_name: `${businessName} Receptionist`,
};
"""
    },
    [X0 + W, Y0],
))

# ---- 3. Idempotency check (Switch) ----
add(node(
    "Check Duplicate Session", "switch",
    {
        "dataType": "string",
        "value1": "0",
        "rules": [{"value2": "0", "regex": ""}],
        "fallbackOutput": "1",
        "options": {},
    },
    [X0 + 2 * W, Y0],
))

# No need for the idempotency check to actually store state in n8n — we'll handle
# it via our backend which has the Stripe session ID. For simplicity, the switch
# lets us add a check later. For now just pass through.

# ---- 4. Knowledge Base ----
add(node(
    "Create Knowledge Base", "httpRequest",
    {
        "method": "POST",
        "url": "https://api.retellai.com/create-knowledge-base",
        "authentication": "genericCredential",
        "nodeCredentialName": "retellApi",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "knowledge_base_name",
                    "value": "={{ $json.kb_name }}",
                },
                {
                    "name": "knowledge_base_texts",
                    "value": "={{ $json.knowledge_base_texts | parseJson }}",
                },
            ],
        },
        "options": {
            "timeout": 15000,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 10000,
        },
    },
    [X0 + 2 * W, Y0 + H],
))

# ---- 5. LLM ----
add(node(
    "Create Retell LLM", "httpRequest",
    {
        "method": "POST",
        "url": "https://api.retellai.com/create-retell-llm",
        "authentication": "genericCredential",
        "nodeCredentialName": "retellApi",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "general_prompt",
                    "value": "={{ $json.general_prompt }}",
                },
                {
                    "name": "general_tools",
                    "value": [
                        {
                            "type": "transfer_call",
                            "name": "transfer_to_human",
                            "description": "Transfer the call to a human team member when the customer needs personal assistance.",
                            "transfer_destination": {
                                "type": "predefined",
                                "number": "={{ $(\"Parse & Validate Intake\").item.json.business_phone }}",
                            },
                            "transfer_option": {"type": "cold_transfer"},
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
                        {
                            "type": "custom",
                            "name": "lookup_caller",
                            "url": "https://owlbell-api-production.up.railway.app/api/v1/agent/tools/lookup-caller",
                            "method": "POST",
                            "description": "Look up a caller by their phone number.",
                            "headers": {"Authorization": "Bearer {{ $env.RETELL_AGENT_TOOLS_SECRET }}"},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "phone_number": {"type": "string", "description": "Caller's phone number in E.164 format"}
                                },
                                "required": ["phone_number"],
                            },
                            "speak_during_execution": True,
                            "speak_after_execution": True,
                            "execution_message_description": "Let me check our records for you.",
                            "args_at_root": True,
                        },
                        {
                            "type": "custom",
                            "name": "qualify_lead",
                            "url": "https://owlbell-api-production.up.railway.app/api/v1/agent/tools/qualify-lead",
                            "method": "POST",
                            "description": "Score and log a lead after collecting service, urgency, and contact info.",
                            "headers": {"Authorization": "Bearer {{ $env.RETELL_AGENT_TOOLS_SECRET }}"},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "caller_name": {"type": "string", "description": "Caller's full name"},
                                    "caller_phone": {"type": "string", "description": "Caller's phone number in E.164 format"},
                                    "service": {"type": "string", "description": "Service needed (hvac, plumbing, electrical, roofing, general)"},
                                    "urgency": {"type": "string", "description": "Urgency level: emergency, asap, or flexible"},
                                    "address": {"type": "string", "description": "Caller's address / location (optional)"},
                                    "notes": {"type": "string", "description": "Any additional context (optional)"},
                                },
                                "required": ["caller_name", "caller_phone", "service", "urgency"],
                            },
                            "speak_during_execution": True,
                            "speak_after_execution": True,
                            "execution_message_description": "Let me log that information for our team.",
                            "args_at_root": True,
                        },
                        {
                            "type": "custom",
                            "name": "check_availability",
                            "url": "https://owlbell-api-production.up.railway.app/api/v1/agent/tools/check-availability",
                            "method": "POST",
                            "description": "Check available 30-minute appointment slots for a given date.",
                            "headers": {"Authorization": "Bearer {{ $env.RETELL_AGENT_TOOLS_SECRET }}"},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
                                },
                                "required": ["date"],
                            },
                            "speak_during_execution": True,
                            "speak_after_execution": True,
                            "execution_message_description": "Let me check what times we have available.",
                            "args_at_root": True,
                        },
                        {
                            "type": "custom",
                            "name": "book_appointment",
                            "url": "https://owlbell-api-production.up.railway.app/api/v1/agent/tools/book-appointment",
                            "method": "POST",
                            "description": "Book an appointment after caller chooses date and time.",
                            "headers": {"Authorization": "Bearer {{ $env.RETELL_AGENT_TOOLS_SECRET }}"},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "caller_name": {"type": "string", "description": "Caller's full name"},
                                    "caller_phone": {"type": "string", "description": "Caller's phone number in E.164 format"},
                                    "service": {"type": "string", "description": "Service needed"},
                                    "date": {"type": "string", "description": "Appointment date in YYYY-MM-DD format"},
                                    "time": {"type": "string", "description": "Appointment start time in HH:MM format (24-hour)"},
                                    "address": {"type": "string", "description": "Service address (optional)"},
                                    "notes": {"type": "string", "description": "Additional notes (optional)"},
                                },
                                "required": ["caller_name", "caller_phone", "service", "date", "time"],
                            },
                            "speak_during_execution": True,
                            "speak_after_execution": True,
                            "execution_message_description": "Let me book that appointment for you.",
                            "args_at_root": True,
                        },
                        {
                            "type": "custom",
                            "name": "log_message",
                            "url": "https://owlbell-api-production.up.railway.app/api/v1/agent/tools/log-message",
                            "method": "POST",
                            "description": "Save a message from a caller who doesn't want to book.",
                            "headers": {"Authorization": "Bearer {{ $env.RETELL_AGENT_TOOLS_SECRET }}"},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "caller_name": {"type": "string", "description": "Caller's full name"},
                                    "caller_phone": {"type": "string", "description": "Caller's phone number in E.164 format"},
                                    "message": {"type": "string", "description": "The message the caller wants to leave"},
                                    "email": {"type": "string", "description": "Caller's email address (optional)"},
                                },
                                "required": ["caller_name", "caller_phone", "message"],
                            },
                            "speak_during_execution": True,
                            "speak_after_execution": True,
                            "execution_message_description": "Let me save that message for our team.",
                            "args_at_root": True,
                        },
                    ],
                },
                {
                    "name": "start_speaker",
                    "value": "agent",
                },
                {
                    "name": "begin_message",
                    "value": "Hi, you've reached {{business_name}}! I'm an AI assistant, and this call may be recorded. How can I help you today?",
                },
                {
                    "name": "model",
                    "value": "gpt-4.1-mini",
                },
                {
                    "name": "model_temperature",
                    "value": 0.4,
                },
            ],
        },
        "options": {
            "timeout": 30000,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 10000,
        },
    },
    [X0 + 3 * W, Y0],
))

# ---- 6. Attach KB to LLM ----
add(node(
    "Attach KB to LLM", "httpRequest",
    {
        "method": "POST",
        "url": "https://api.retellai.com/update-retell-llm/{{ $json.llm_id }}",
        "authentication": "genericCredential",
        "nodeCredentialName": "retellApi",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "knowledge_base_ids",
                    "value": ["={{ $(\"Create Knowledge Base\").item.json.knowledge_base_id }}"],
                },
            ],
        },
        "options": {
            "timeout": 15000,
            "retryOnFail": True,
            "maxTries": 2,
        },
    },
    [X0 + 3 * W, Y0 + H],
))

# ---- 7. Create Agent ----
add(node(
    "Create Agent", "httpRequest",
    {
        "method": "POST",
        "url": "https://api.retellai.com/create-agent",
        "authentication": "genericCredential",
        "nodeCredentialName": "retellApi",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "agent_name",
                    "value": "={{ $(\"Parse & Validate Intake\").item.json.agent_name }}",
                },
                {
                    "name": "response_engine",
                    "value": {
                        "type": "retell-llm",
                        "llm_id": "={{ $json.llm_id }}",
                    },
                },
                {
                    "name": "voice_id",
                    "value": "retell-Willa",
                },
                {
                    "name": "webhook_url",
                    "value": "https://owlbell-api-production.up.railway.app/api/v1/webhooks/retell",
                },
                {
                    "name": "webhook_events",
                    "value": ["call_started", "call_ended", "call_analyzed"],
                },
                {
                    "name": "language",
                    "value": "en-US",
                },
                {
                    "name": "enable_backchannel",
                    "value": True,
                },
                {
                    "name": "interruption_sensitivity",
                    "value": 0.7,
                },
                {
                    "name": "responsiveness",
                    "value": 0.8,
                },
                {
                    "name": "end_call_after_silence_ms",
                    "value": 30000,
                },
                {
                    "name": "max_call_duration_ms",
                    "value": 1800000,
                },
            ],
        },
        "options": {
            "timeout": 30000,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 10000,
        },
    },
    [X0 + 4 * W, Y0],
))

# ---- 8. Create Phone Number ----
add(node(
    "Create Phone Number", "httpRequest",
    {
        "method": "POST",
        "url": "https://api.retellai.com/create-phone-number",
        "authentication": "genericCredential",
        "nodeCredentialName": "retellApi",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "agent_id",
                    "value": "={{ $json.agent_id }}",
                },
                {
                    "name": "area_code",
                    "value": "={{ $(\"Parse & Validate Intake\").item.json.area_code }}",
                },
            ],
        },
        "options": {
            "timeout": 30000,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 10000,
        },
    },
    [X0 + 4 * W, Y0 + H],
))

# ---- 9. Publish Agent ----
add(node(
    "Publish Agent", "httpRequest",
    {
        "method": "POST",
        "url": "https://api.retellai.com/update-agent/{{ $json.agent_id }}",
        "authentication": "genericCredential",
        "nodeCredentialName": "retellApi",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "is_published",
                    "value": True,
                },
            ],
        },
        "options": {
            "timeout": 15000,
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 10000,
        },
    },
    [X0 + 5 * W, Y0],
))

# ---- 10. Log provisioning ----
add(node(
    "Log Provisioning Complete", "code",
    {
        "jsCode": """// Log the provisioning result
const agent = $input.first().json;
const meta = $("Parse & Validate Intake").item.json;
const phone = $("Create Phone Number").item.json;

// Build provision record
const record = {
  event: 'provisioning.complete',
  timestamp: new Date().toISOString(),
  session_id: meta.session_id,
  business_name: meta.business_name,
  customer_email: meta.customer_email,
  agent_id: agent.agent_id,
  phone_number: phone.phone_number || phone.inbound_phone_number || 'assigned',
  status: 'active',
};

console.log('PROVISIONING COMPLETE:', JSON.stringify(record, null, 2));
return record;
"""
    },
    [X0 + 5 * W, Y0 + H],
))

# ---- 11. Send Welcome Email ----
add(node(
    "Send Welcome Email", "gmail",
    {
        "resource": "message",
        "operation": "send",
        "to": "={{ $(\"Parse & Validate Intake\").item.json.customer_email }}",
        "subject": "={{ \"Your \" + $(\"Parse & Validate Intake\").item.json.business_name + \" AI Receptionist Is Live!\" }}",
        "messageType": "html",
        "message": (
            "=<h2>Your AI Receptionist is Ready!</h2>"
            "<p>Great news — your Retell AI phone agent for <strong>{{ $(\"Parse & Validate Intake\").item.json.business_name }}</strong> is now live!</p>"
            "<p><strong>Your new business number:</strong> <big>{{ $(\"Create Phone Number\").item.json.phone_number || $(\"Create Phone Number\").item.json.inbound_phone_number }}</big></p>"
            "<p>Your AI receptionist will answer calls 24/7, qualify leads, book appointments, and take messages — all in English and Spanish.</p>"
            "<hr>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Forward your existing business number to the new number above, or start using it directly</li>"
            "<li>Test your agent by calling the number</li>"
            "<li>Log in to the <a href=\"https://app.owlbell.xyz\">Owlbell Dashboard</a> to view calls, leads, and analytics</li>"
            "</ol>"
            "<p>Need help? Reply to this email or visit our help center.</p>"
            "<p>— The Owlbell Team</p>"
        ),
    },
    [X0 + 6 * W, Y0],
    extras={
        "credentials": {
            "gmailOAuth": {
                "id": uid(),
                "name": "Gmail API",
            },
        },
    },
))

# ---- 12. Send SMS ----
add(node(
    "Send Welcome SMS", "twilio",
    {
        "resource": "sms",
        "operation": "send",
        "to": "={{ $(\"Parse & Validate Intake\").item.json.business_phone }}",
        "from": "={{ $(\"Create Phone Number\").item.json.phone_number || $(\"Create Phone Number\").item.json.inbound_phone_number }}",
        "message": "={{ \"Your \" + $(\"Parse & Validate Intake\").item.json.business_name + \" AI receptionist is live! Your number: \" + ($(\"Create Phone Number\").item.json.phone_number || $(\"Create Phone Number\").item.json.inbound_phone_number) + \". Log in: https://app.owlbell.xyz\" }}",
    },
    [X0 + 6 * W, Y0 + H],
    extras={
        "credentials": {
            "twilioApi": {
                "id": uid(),
                "name": "Twilio Account",
            },
        },
    },
))

# (Optional node — add between Check Duplicate Session output 1 and this
#  to handle duplicate Stripe sessions gracefully.)
# add(node("Already Provisioned (Skip)", "noOp", {}, [X0 + 3 * W, Y0 + 2 * H]))

# ---- 13. Error Handler (catch "already published" errors) ----
add(node(
    "Handle Publish Error", "code",
    {
        "jsCode": """// Handle "cannot update published flow" errors
const error = $input.first().json.error || {};
const errorMessage = error.message || JSON.stringify(error);

if (errorMessage.includes('published') || errorMessage.includes('cannot update')) {
  // Draft from the published version instead of failing
  console.log('Agent already published — drafting from published version');
  return {
    action: 'already_published',
    message: 'Agent was already published. No changes needed.',
    status: 'ok',
  };
}

// Otherwise rethrow
throw new Error(`Publish failed: ${errorMessage}`);
"""
    },
    [X0 + 5 * W, Y0 + 2 * H],
))

# ---------------------------------------------------------------------------
# Define connections between nodes
# ---------------------------------------------------------------------------
# Main provisioning chain
link("Stripe Webhook", "Parse & Validate Intake")
link("Parse & Validate Intake", "Check Duplicate Session")
link("Check Duplicate Session", "Create Knowledge Base", 0)     # new session → provision
# NOTE: Configuring output 1 as a duplicate-skip requires a proper idempotency
# check (e.g., lookup session ID in a db). Without it, n8n's Switch fallback
# output routes unmatched sessions here. Either remove the connection or
# add a real check.
link("Create Knowledge Base", "Create Retell LLM")
link("Create Retell LLM", "Attach KB to LLM")
link("Attach KB to LLM", "Create Agent")
link("Create Agent", "Create Phone Number")
link("Create Phone Number", "Publish Agent")
link("Publish Agent", "Log Provisioning Complete")
link("Log Provisioning Complete", "Send Welcome Email", 0)
link("Log Provisioning Complete", "Send Welcome SMS", 1)

# Publish error → draft recovery
link("Publish Agent", "Handle Publish Error", 1)  # error output → recovery

# ---------------------------------------------------------------------------
# Build connections map from edges
# ---------------------------------------------------------------------------
connections = {}
for e in edges:
    from_name = e["from"]
    if from_name not in connections:
        connections[from_name] = {"main": []}
    # Ensure enough output slots
    while len(connections[from_name]["main"]) <= e["fromOutputIndex"]:
        connections[from_name]["main"].append([])

    connections[from_name]["main"][e["fromOutputIndex"]].append({
        "node": e["to"],
        "type": "main",
        "index": e["toInputIndex"],
    })

# ---------------------------------------------------------------------------
# Build the workflow
# ---------------------------------------------------------------------------
workflow = {
    "name": "🦉 Owlbell — Auto-Provision Retell Agent",
    "nodes": nodes,
    "connections": connections,
    "pinData": {},
    "versionId": uid(),
    "active": False,
    "settings": {
        "executionOrder": "v1",
        "timezone": "UTC",
    },
    "staticData": None,
    "tags": [
        {"name": "provisioning", "id": uid()},
        {"name": "retell", "id": uid()},
        {"name": "stripe", "id": uid()},
    ],
}

# Write output
output_path = __file__.replace("generate-workflow.py", "retell-provisioning.json")
with open(output_path, "w") as f:
    json.dump(workflow, f, indent=2)

print(f"Workflow written to: {output_path}")
print(f"  Nodes: {len(nodes)}")
print(f"  Connections: {len(edges)}")
print()
print("To import into n8n:")
print("  1. Open n8n -> Workflows -> Import from File")
print(f"  2. Select {output_path}")
print()
print("  3. Create required credentials in n8n:")
print("     +-------------------------------------------------------------+")
print("     |  retellApi  (Generic Credential / Header Auth)              |")
print("     |  Name:  Retell API                                          |")
print("     |  Type:  Generic Credential                                  |")
print("     |  Auth:  Header Auth                                         |")
print("     |  Name:  X-API-Key                                           |")
print("     |  Value: <your_retell_api_key_here>                          |")
print("     +-------------------------------------------------------------+")
print()
print("     +-------------------------------------------------------------+")
print("     |  gmailOAuth  (Gmail OAuth2)                                 |")
print("     |  Set up Gmail OAuth2 via n8n credential wizard              |")
print("     |  Requires: client_id, client_secret, refresh_token          |")
print("     |  Or use your existing Gmail OAuth from Owlbell .env:        |")
print("     |    INTEGRATION_GMAIL_CLIENT_ID, ..._SECRET, ..._REFRESH_TOKEN|")
print("     +-------------------------------------------------------------+")
print()
print("     +-------------------------------------------------------------+")
print("     |  twilioApi  (Twilio Account)                                |")
print("     |  Account SID:  <your_twilio_account_sid>                        |")
print("     |  Auth Token:  <your_twilio_auth_token>                      |")
print("     |  From number: <your_twilio_phone_number>                    |")
print("     |  (Same as INTEGRATION_TWILIO_ACCOUNT_SID / AUTH_TOKEN)      |")
print("     +-------------------------------------------------------------+")
print()
print("  4. Set environment variables in n8n (Settings -> Env):")
print("     RETELL_AGENT_TOOLS_SECRET=<same value as INTEGRATION_RETELL_AGENT_TOOLS_SECRET>")
print("     (Optional) STRIPE_WEBHOOK_SECRET=<your Stripe webhook signing secret>")
print()
print("  5. Configure the Stripe webhook endpoint in Stripe Dashboard:")
print("     Endpoint URL: https://<your-n8n-host>/webhook/stripe-checkout-completed")
print("     Events:      checkout.session.completed")
print("     (Stripe sends this when a customer completes checkout)")
print()
print("  6. Activate the workflow")
