### Versions

**0.2.3**
- Add ROADMAP.md (included in documentation)
- Add *pyjs8call.settings.Settings.load()* to load settings from an ini file (see example *settings.ini* in repo)
- Add CLI support for usage like *python -m pyjs8call* (try *--help* for options)
- Add CLI documentation to README
- Add RNS PipeInterface support using *python -m pyjs8call --rns* CLI option
- Add *restore_on_exit* argument to *pyjs8call.settings.Settings.set_profile()*
- Add *pyjs8call.message.Message.encode()* and *pyjs8call.message.Message.decode()* for handling byte data
- Add notification type enable/disable functions in *pyjs8call.notifications*
- Add *terminate_js8call* argument to *pyjs8call.client.Client.stop()*
- Add *pyjs8call.settings.Settings.create_new_profile()*
- Add *create* argument to *pyjs8call.settings.Settings.set_profile()*
- Add support for user home directory (~/) in JS8Call configuration file path
- Add *normalize_snr* argument to *propagation* functions
- Add lat/lon to grid-based datasets in *propagation*
- Add *pyjs8call.client.Client.get_call_activity_from_spots()* to improve processing speed
- Separate *pyjs8call.settings.Settings* and *pyjs8call.callbacks.Callbacks* into separate modules
- Add *pyja8call.callbacks.restart_complete* callback function
- Add *restart* attribute to *pyjs8call.schedulemonitor.ScheduleEntry* objects to allow forced restart on a schedule
- Remove JS8Call *timer.out* file when starting (or restarting) to avoid large file size over time
- Add *pyjs8call.settings.Settings* functions related to daily application restart (to remove *timer.out*)
- Add *best_band_for_grid()* and *best_band_for_origin()* functions to *pyjs8call.propagation.Propagation*
- Add *client.Client.heard_freq_bands()* function
- Enable JS8Call heartbeat networking when *pyjs8call* heartbeat networking is enabled
- Enable JS8Call heartbeat networking when heartbeat acknowledgements are enabled
- Add *pyjs8call.client.Client.autodetect_outgoing_directed_command* to simplify app development
- @TIME group no longer added by default
- Replace *pyjs8call.message.Message.time* with *pyjs8call.message.Message.utc_time_str*
- Fix bug preventing setting of station info
- Fix bug causing comma in empty groups field
- Fix bug causing *pyjs8call* exit tasks to be run when restarting JS8Call application
- Fix bug in inbox message timestamp parsing
- Documentation improvements

**0.2.2**
- Add *pyjs8call.propagation* module
- Add *pyjs8call.notifications* module
- Fix bug when JS8Call is running before pyjs8call is started on Windows (see discussion #1)
- Fix intermittent transmission of heartbeat messages outside of sub-band
- Improve pyjs8call heartbeat interval timing and utilize config file heartbeat interval
- Prevent pyjs8call heartbeat networking in turbo mode and when a callsign is selected on the JS8Call UI
- Add additional configuration management functions to *pyjs8call.client.settings*
- Write configuration to file on *pyjs8call.client* stop, including JS8Call application exit
- Read/write persistent *pyjs8call.client* attributes to/from configuration on init/stop
- Update *pyjs8call.message* autoreply commands
- Detect JS8Call autoreplies as outgoing activity
- Prevent past schedule entries running when *pyjs8call.client.schedule* re-enabled
- Store schedule changes in configuration file and load on init
- Improve rx text box message processing in *pyjs8call.client.get_rx_messages*
- Add spot get/set functions to *pyjs8call.js8call* to facilitate import/export
- Change spot limit from quantity-based to time-based
- Add grid, dial frequency, and frequency band spot filters to *pyjs8call.spotmonitor.filter*
- Allow multiple callbacks for spots, station spots, and group spots in *pyjs8call.client.callback*
- Add frequency/band conversion convenience functions to *pyjs8call.client*
- Track frequency/band changes
- Track last incoming/outgoing message timestamp by band
- Add *pyjs8call.client.station_hearing* and *pyjs8call.client.station_heard_by* functions
- Manage periodic local state updates in *pyjs8call.js8call* instead of individual modules
- Stability improvements
- Minor bug fixes
- Minor documentation improvements

**0.2.1**
- Fix *pyjs8call.Message.text* being overwritten during object initialization
- Fix intermittent *NoneType* error in *pyjs8call.js8call* transmit function
- Fix removal of incorrect message from outgoing queue due to incorrect equality logic
- Fix *IndexError* in *pyjs8call.offsetmonitor* when no unused spectrum is found
- Change the maximum time to wait for a socket connection during JS8Call application start to 120 seconds
- Improve JS8Call application start process by waiting for socket response (supports slower SBCs)
- Change minimum limit for *pyjs8call.Client.settings.set_idle_timeout* to zero (idle timeout disabled)
- Remove idle monitor module (not needed, set timeout to zero to disable)
- Add *enabled*, *paused*, *pause*, and *resume* functions to all internal modules
- Rename module *enable* and *disable* functions as needed for consistency
- Rename *pyjs8call.Client.drift* to *pyjs8call.Client.drift_sync*
- Add *hb* argument to *pyjs8call.Client.identities*
- Add *pyjs8call.Client.settings* configuration profile functions
- Add *pyjs8call.Client.settings* distance units functions
- Add *pyjs8call.message* default attributes *tdrift*, *profile*, *error*, and *local_time_str*
- Set spotted message *status* to *Message.STATUS_RECEIVED*
- Set incoming and outgoing message *profile* attribute to the active configuration profile
- Add *profile* argument to the *pyjs8call.spotmonitor.filter* function
- Change message type used by *pyjs8call.windowmonitor* from *TX_FRAME* to *RIG_PTT*
- Improve JS8Call "ping" (application connectivity check) handling
- Add *pyjs8call.Client.heard_by* function
- Improve *pyjs8call.Client.hearing* command handling and aging
- Add additional information to *pyjs8call.Client.get_call_activity*
- Fix message value handling for various JS8Call transmit messages type
- Add support for JS8Call command line arguments
- Add necessary config file handling when rig name command line argument is specified
- Change default application close action to exit instead of automatic restart
- Improve internal restart handling
- Implement support for custom processing of incoming and outgoing messages
- Add *pyjs8call.schedulemonitor*
- Change minimum Python version to 3.6.1
- Stability improvements
- Minor bug fixes
- Minor documentation improvements

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
