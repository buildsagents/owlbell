Owlbell sample call audio - served at /demos/plumbing-emergency-sample.mp3

Source: fallback script walkthrough for browsers that cannot start the live Retell web call.
Transcript source: src/lib/demo-call-data.ts
Live demo source: /api/demo/web-call creates a Retell web call and the browser connects with retell-client-js-sdk.

Concatenate after converting clips to WAV:
  ffmpeg -f concat -safe 0 -i concat.txt -af "loudnorm=I=-18:LRA=11:TP=-1.5" -ar 24000 -ac 1 -codec:a libmp3lame -b:a 96k ../plumbing-emergency-sample.mp3
