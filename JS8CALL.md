### Recommended JS8Call Improvements

API support for enabling/disabling heartbeats. At a minimum utilize the specified offset when handling network messages with type 'TX.SEND_MESSAGE'. This would allow messages to be sent at a specific offset, including heartbeats.

When handling network messages with type 'MODE.GET_SPEED' set variable m_nSubMode so actual modem sspeed is changed. Only the UI is updated currently.


