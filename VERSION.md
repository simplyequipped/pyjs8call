### Versions

**0.2.1**
- Fix *pyjs8call.Message.text* being overwritten during object initialization
- Set spotted message *status* to *Message.STATUS_RECEIVED*
- Change the maximum time to wait for a socket connection during JS8Call application start to 120 seconds
- Change minimum limit for *pyjs8call.Client.settings.set_idle_timeout* to zero (idle timeout disabled)
- Remove idle monitor module
- Improve JS8Call application start process by waiting for socket response (supports slower SBCs)
- Improve restarting process by reinitializing local state as soon as possible
- Improve restarting process by delaying local state update requests (avoids errors)
- Improve restarting process by pausing internal module operations (avoids errors)
- Add *enabled*, *paused*, *pause*, and *resume* functions to all internal modules

**0.2.0**

- Add *psutil* package requirement
- Add cross-platform support for Linux, Windows, and MacOS
- Improve error handling during start/stop/restart
- Minor bug fixes
- Minor documentation improvements

**0.1.2**

- Rename pyjs8call.txmonitor to pyjs8call.outgoingmonitor
- Rename pyjs8call.hbmonitor to pyjs8call.hbnetwork
- Rename several module enable/disable/pause/resume functions
- Reorganize several pyjs8call.client functions into pyjs8call.client.Settings
- Reorganize spot related function under pyjs8call.spotmonitor
- pyjs8call.client function *get_spots* moved to pyjs8call.spotmonitor *filter*
- Improve efficiency by reducing JS8Call API calls in pyjs8call.client.Settings *get* functions
- Rename pyjc8call.client function *get_tx_window_duration* to *get_window_duration*
- pyjs8call.client function *set_station_callsign* no longer restarts JS8Call automatically
- Improve pyjs8call.client function *hearing* by including heartbeat acknowledgements
- Add pyjs8call.client functions *reset_when_inactive*, *activity*, and *grid_distance*
- Change the log message format to use the pyjs8call.message function *dump*
- Change pyjs8call.windowmonitor function *next_transition_seconds* arguments to *cycles* and *default*
- Change pyjs8call.windowmonitor function *next_transition_timestamp* arguments to *cycles* and *default*
- Add pyjs8call.windowmonitor function *sleep_until_next_transition*
- Set *distance* and *bearing* attributes in pyjs8call.message objects when *grid* attribute is set
- Implement offset QSY to the heartbeat sub-band while sending heartbeat messages via pyjs8call.hbnetwork
- pyjs8call.windowmonitor now continues to use incoming messages after receiving a tx frame
- Minor bug fixes
- Documentation improvements
- Updated documentation examples and example.py

**0.1.1**

- Increase pyjs8call.js8call default maximum spots to 5000
- Replace *pyjs8call.spot* with pyjs8call.message, eliminating the *pyjs8call.spot* object
- Improve pyjs8call.spotmonitor efficiency by checking spots at each rx/tx window transition
- Add group spot management functions in pyjs8call.spotmonitor
- Add callback function for group spots
- Add callback function for new inbox messages
- Improve callback handling by calling functions using *threading.Thread*
- Improve restart handling by not reinitializing modules unnecessarily
- Improve restart handling by saving and restoring internal configuration and state without restarting sub-modules
- Improve message parsing for specific types and commands
- Add all JS8Call message types and commands to pyjs8call.message
- Improve pyjs8call.windowmonitor by utilizing incoming messages in addition to outgoing tx frames
- Add pyjs8call.client.Settings with common configuration file management functions
- Add pyjs8call.timemonitor module for syncing time drift and managing time master stations
- Add pyjs8call.hbmonitor module for automating heartbeat messages
- Add pyjs8call.inboxmonitor module for local inbox message handling and syncing of remote inbox messages
- Add pyjs8call.client.Callbacks which replaces module-specific callback functions
- Add pyjs8call.client.Client.hearing function to parse spots for network mapping
- Add multiple pyjs8call.client query message functions
- Improve pyjs8call.client outgoing message functions to support relay destinations
- Improvements per pylint
- Documentation improvements
- Update documentation examples and example.py

**0.1.0**

Initial publicly released version.
