Drop your sample call recordings here, then run `python build_site.py`.

The landing page (founding_page.html) references these exact filenames:
  - emergency.mp3   (after-hours burst-pipe / emergency call)
  - booking.mp3     (appointment booking call)
  - pricing.mp3     (price-inquiry call)

Anything in site/public/ is copied to the deployed site root, so these end up at
/demos/emergency.mp3, /demos/booking.mp3, /demos/pricing.mp3 — which is what the
<audio> players on the page point to.

How to make the recordings (fastest):
  1. Set up your Twilio/Telnyx demo number and enable recording.
  2. Call it 3 times and run the emergency / booking / pricing scripts
     (the transcripts shown on the page match these scenarios).
  3. Download the recordings, rename to the filenames above, drop them here, rebuild.

Until you add them, the audio players show but won't play — the transcripts on the
page carry the proof on their own.
