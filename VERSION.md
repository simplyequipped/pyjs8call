### Versions

**0.1.0**

Initial publicly released version.

**0.1.1** (WIP)

- Increase pyjs8call.js8call default maximum spots to 5000
- Replace pyjs8call.spot with pyjs8call.message, eliminating pyjs8call.spot
- Improve pyjs8call.spotmonitor efficiency by checking spots at each rx/tx window transition
- Replace various callback functions with the pyjs8call.client.Callbacks class
- Improve callback handling by calling functions using *threading.Thread*
- Improve restart handling by not reinitializing modules unnecessarily
- Improve restart handling by saving and restoring internal configuration and state
- Improve pyjs8call.windowmonitor by utilizing incoming messages in addition to outgoing messages
- Add callback function for group specific spots
- Add pyjs8call.timemonitor module for syncing time drift and managing time master stations
- Add pyjs8call.hbmonitor module for automating heartbeat messages
- Improvements per pylint
- Documentation improvements
- Update examples and example.py

