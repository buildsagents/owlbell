"""Check available Retell voices and test API."""
import os, json
from dotenv import load_dotenv
load_dotenv()

from retell import Retell

client = Retell(api_key=os.environ["INTEGRATION_RETELL_API_KEY"])

# Check what attributes the client has
print("Client attributes:", [x for x in dir(client) if not x.startswith('_')])
print()

# List voices via SDK
try:
    voices = client.voice.list()
    print("Voice list type:", type(voices))
    if isinstance(voices, list):
        for v in voices[:25]:
            print(f"  {v.get('voice_id')}: {v.get('voice_name', v.get('name', '?'))}")
    else:
        print("Voice list:", json.dumps(voices, indent=2)[:2000])
except Exception as e:
    print(f"SDK voice.list error: {e}")

# Try REST API directly
import requests
resp = requests.get(
    "https://api.retellai.com/list-voices",
    headers={"Authorization": f"Bearer {os.environ['INTEGRATION_RETELL_API_KEY']}"}
)
print(f"\nREST /list-voices: {resp.status_code}")
if resp.ok:
    data = resp.json()
    voices = data if isinstance(data, list) else data
    for v in voices[:25]:
        voice_id = v.get("voice_id", "?")
        name = v.get("voice_name", v.get("name", "?"))
        provider = v.get("provider", v.get("llm_provider", "?"))
        print(f"  {voice_id}: {name} ({provider})")
else:
    print(resp.text[:500])

# Check list of available models
print("\n---")
resp2 = requests.get(
    "https://api.retellai.com/list-models",
    headers={"Authorization": f"Bearer {os.environ['INTEGRATION_RETELL_API_KEY']}"}
)
print(f"REST /list-models: {resp2.status_code}")
if resp2.ok:
    print(resp2.json())
