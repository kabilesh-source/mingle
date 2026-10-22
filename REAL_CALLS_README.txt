REAL AUDIO / VIDEO CALLS
1. Start app and log in with two DIFFERENT registered accounts on two browsers/devices.
2. Both must have the app open (calls are polled every 1.2 seconds).
3. Select the other REAL user in Messages and press Audio or Video.
4. Receiver gets an incoming call confirmation; accept and grant mic/camera access.
5. Calls use WebRTC peer-to-peer; this demo uses public STUN only.
IMPORTANT: For two devices, deploy on HTTPS. localhost works only on the same computer.
For production reliability across carrier/mobile NATs, configure a TURN server in rtcConfig in public/index.html. Public STUN alone does not guarantee connections.
The signaling server keeps events in RAM; restarting it loses pending calls. This is a starter implementation, not a production calling system.
DEMO profiles cannot receive calls. Do not use fake users as test callees.
