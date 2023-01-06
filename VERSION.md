### Versions

**0.1.0**

Initial publicly released version.

**0.1.1** (WIP)

- Increase pyjs8call.js8call default maximum spots to 5000
- Replace pyjs8call.spot with pyjs8call.message, eliminating pyjs8call.spot
- Improve pyjs8call.spotmonitor efficiency by checking spots at each rx/tx window transition
- Replace various callback functions with the pyjs8call.client.Callbacks class
- Improve callback handling by calling functions using *threading.Thread*
- Revise pyjs8call.windowmointor to utilize incoming messages in addition to outgoing messages
- Minor documentation improvements
- Update examples and example.py

