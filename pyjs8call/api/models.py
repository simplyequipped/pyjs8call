# MIT License
# 
# Copyright (c) 2022-2025 Simply Equipped
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''Pydantic models for API request/response serialization.'''

__docformat__ = 'google'

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class MessageModel(BaseModel):
    '''Message object for API serialization.'''
    
    # core message fields
    id: Optional[str] = None
    type: Optional[str] = None
    timestamp: Optional[float] = None
    
    # station information
    origin: Optional[str] = None
    destination: Optional[str] = None
    call: Optional[str] = None
    grid: Optional[str] = None
    
    # message content
    text: Optional[str] = None
    value: Optional[str] = None
    cmd: Optional[str] = None
    
    # technical details
    freq: Optional[int] = None
    dial: Optional[int] = None
    offset: Optional[int] = None
    snr: Optional[float] = None
    speed: Optional[str] = None
    tdrift: Optional[float] = None
    
    # location/distance
    distance: Optional[int] = None
    distance_units: Optional[str] = None
    bearing: Optional[int] = None
    
    # status/routing
    status: Optional[str] = None
    path: Optional[List[str]] = None
    profile: Optional[str] = None
    error: Optional[str] = None
    
    # time fields
    utc: Optional[str] = None
    utc_time_str: Optional[str] = None
    local_time_str: Optional[str] = None
    
    # complex data fields
    hearing: Optional[List[str]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    band_activity: Optional[List[Dict[str, Any]]] = None
    call_activity: Optional[List[Dict[str, Any]]] = None
    
    # additional fields
    extra: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

    @classmethod
    def from_pyjs8call_message(cls, msg):
        '''Convert pyjs8call Message object to API model.
        
        Args:
            msg: pyjs8call.message.Message object
            
        Returns:
            MessageModel: API-serializable message model
        '''
        data = {}
        
        # extract all attributes that exist on the message
        for attr in msg.attributes:
            value = getattr(msg, attr, None)
            if value is not None:
                data[attr] = value
                
        return cls(**data)


class SendMessageRequest(BaseModel):
    '''Request model for sending messages.'''
    destination: str = Field(..., description='Destination callsign')
    message: str = Field(..., description='Message text to send')


class SendDirectedCommandRequest(BaseModel):
    '''Request model for sending directed command messages.'''
    destination: str = Field(..., description='Destination callsign')
    command: str = Field(..., description='Command to send')
    message: Optional[str] = Field(None, description='Optional message text')


class SendRawMessageRequest(BaseModel):
    '''Request model for sending raw messages.'''
    message: str = Field(..., description='Raw message text to send')


class SendDirectedBytesRequest(BaseModel):
    '''Request model for sending directed bytes messages.'''
    destination: str = Field(..., description='Destination callsign')
    data: str = Field(..., description='Base64 encoded bytes data to send')


class SendInboxMessageRequest(BaseModel):
    '''Request model for sending inbox messages.'''
    destination: str = Field(..., description='Destination callsign')
    message: str = Field(..., description='Message text to send')


class StoreInboxMessageRequest(BaseModel):
    '''Request model for storing inbox messages.'''
    origin: str = Field(..., description='Origin callsign')
    destination: str = Field(..., description='Destination callsign')
    message: str = Field(..., description='Message text to store')
    path: Optional[str] = Field(None, description='Message relay path')
    remote: bool = Field(False, description='Whether message is from remote source')


class SendQueryRequest(BaseModel):
    '''Request model for sending query messages.'''
    destination: str = Field(..., description='Destination callsign or group')


class QueryCallRequest(BaseModel):
    '''Request model for sending callsign query.'''
    callsign: str = Field(..., description='Callsign to query for')
    destination: str = Field('@ALLCALL', description='Destination for query')


class QueryMessagesRequest(BaseModel):
    '''Request model for sending stored messages query.'''
    destination: str = Field('@ALLCALL', description='Destination for query')


class QueryMessageIdRequest(BaseModel):
    '''Request model for sending message ID query.'''
    destination: str = Field(..., description='Destination callsign')
    message_id: str = Field(..., description='Message ID to query')


class QueryStationRequest(BaseModel):
    '''Request model for sending station queries (hearing, SNR, grid, info, status).'''
    destination: str = Field(..., description='Destination callsign')
    query_type: str = Field(..., description='Query type: hearing, snr, grid, info, or status')


class SendAPRSGridRequest(BaseModel):
    '''Request model for sending APRS grid message.'''
    grid: Optional[str] = Field(None, description='Grid square to send')


class SendAPRSSMSRequest(BaseModel):
    '''Request model for sending APRS SMS message.'''
    phone: str = Field(..., description='Phone number')
    message: str = Field(..., description='SMS message text')


class SendAPRSEmailRequest(BaseModel):
    '''Request model for sending APRS email message.'''
    email: str = Field(..., description='Email address')
    message: str = Field(..., description='Email message text')


class SendAPRSPOTARequest(BaseModel):
    '''Request model for sending APRS POTA spot.'''
    park: str = Field(..., description='POTA park identifier')
    freq: int = Field(..., description='Frequency in Hz')
    mode: str = Field(..., description='Operating mode')
    message: str = Field(..., description='Spot message')
    callsign: Optional[str] = Field(None, description='Callsign to spot')


class SetFrequencyRequest(BaseModel):
    '''Request model for setting frequency.'''
    frequency: int = Field(..., description='Frequency in Hz')


class SetCallsignRequest(BaseModel):
    '''Request model for setting station callsign.'''
    callsign: str = Field(..., description='Station callsign')


class SetGridRequest(BaseModel):
    '''Request model for setting station grid.'''
    grid: str = Field(..., description='Station grid square')


class SetInfoRequest(BaseModel):
    '''Request model for setting station info.'''
    info: str = Field(..., description='Station info text')


class SetTXTextRequest(BaseModel):
    '''Request model for setting TX text.'''
    text: str = Field(..., description='Text to set in TX field')


class SetOffsetRequest(BaseModel):
    '''Request model for setting frequency offset.'''
    offset: int = Field(..., description='Frequency offset in Hz')


class SetSpeedRequest(BaseModel):
    '''Request model for setting modem speed.'''
    speed: str = Field(..., description='Modem speed: slow, normal, fast, turbo')


class SetStationInfoRequest(BaseModel):
    '''Request model for setting station info.'''
    info: str = Field(..., description='Station info text')


class SetHeartbeatIntervalRequest(BaseModel):
    '''Request model for setting heartbeat interval.'''
    interval: int = Field(..., description='Heartbeat interval in seconds')


class SetIdleTimeoutRequest(BaseModel):
    '''Request model for setting idle timeout.'''
    timeout: int = Field(..., description='Idle timeout in seconds (0 to disable)')


class SetDistanceUnitsRequest(BaseModel):
    '''Request model for setting distance units.'''
    units_miles: bool = Field(..., description='True for miles, False for kilometers')


class SetHighlightWordsRequest(BaseModel):
    '''Request model for setting highlight words.'''
    words: List[str] = Field(..., description='List of highlight words')
    primary: bool = Field(True, description='True for primary, False for secondary highlight words')


class EnableFeatureRequest(BaseModel):
    '''Request model for enabling/disabling features.'''
    feature: str = Field(..., description='Feature name: heartbeat_networking, heartbeat_acknowledgements, multi_decode, autoreply_startup, autoreply_confirmation, allcall, reporting, transmit')
    enabled: bool = Field(..., description='True to enable, False to disable')


class SetDailyRestartRequest(BaseModel):
    '''Request model for setting daily restart.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    restart_time: str = Field('02:00', description='Restart time in HH:MM format')


class SetProfileRequest(BaseModel):
    '''Request model for setting active profile.'''
    profile: str = Field(..., description='Profile name to activate')
    restore_on_exit: bool = Field(False, description='Restore previous profile on exit')
    create: bool = Field(False, description='Create profile if it does not exist')


class CreateProfileRequest(BaseModel):
    '''Request model for creating new profile.'''
    new_profile: str = Field(..., description='Name of new profile to create')
    copy_profile: str = Field('Default', description='Existing profile to copy from')


class SetGroupsRequest(BaseModel):
    '''Request model for setting groups list.'''
    groups: List[str] = Field(..., description='List of group names')


class AddGroupRequest(BaseModel):
    '''Request model for adding a group.'''
    group: str = Field(..., description='Group name to add')


class RemoveGroupRequest(BaseModel):
    '''Request model for removing a group.'''
    group: str = Field(..., description='Group name to remove')


class ModuleControlRequest(BaseModel):
    '''Request model for enabling/disabling modules.'''
    module: str = Field(..., description='Module name: heartbeat, inbox, offset, outgoing, spots, window, schedule, notifications, time')
    enabled: bool = Field(..., description='True to enable, False to disable')


class InboxConfigRequest(BaseModel):
    '''Request model for configuring inbox monitor.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    query: bool = Field(False, description='Enable periodic remote inbox queries')
    destination: str = Field('@ALLCALL', description='Destination for queries')
    interval: int = Field(60, description='Query interval in minutes')


class HeartbeatConfigRequest(BaseModel):
    '''Request model for configuring heartbeat networking.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    interval: Optional[int] = Field(None, description='Custom heartbeat interval in seconds')


class OffsetConfigRequest(BaseModel):
    '''Request model for configuring offset monitor.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    min_offset: Optional[int] = Field(None, description='Minimum offset for adjustment in Hz')
    max_offset: Optional[int] = Field(None, description='Maximum offset for adjustment in Hz') 
    activity_cycles: Optional[float] = Field(None, description='RX/TX cycles to consider recent activity')
    bandwidth_safety_factor: Optional[float] = Field(None, description='Safety factor around signal bandwidth')


class SpotsConfigRequest(BaseModel):
    '''Request model for configuring spots monitor.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    watched_stations: Optional[List[str]] = Field(None, description='List of station callsigns to watch')
    watched_groups: Optional[List[str]] = Field(None, description='List of group designators to watch')


class NotificationsConfigRequest(BaseModel):
    '''Request model for configuring notifications.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    incoming_enabled: Optional[bool] = Field(None, description='Notify on incoming directed messages')
    spots_enabled: Optional[bool] = Field(None, description='Notify on all spots')
    station_spots_enabled: Optional[bool] = Field(None, description='Notify on watched station spots')
    group_spots_enabled: Optional[bool] = Field(None, description='Notify on watched group spots')
    smtp_email: Optional[str] = Field(None, description='SMTP email address')
    smtp_password: Optional[str] = Field(None, description='SMTP password')
    smtp_server: Optional[str] = Field(None, description='SMTP server address')
    smtp_port: Optional[int] = Field(None, description='SMTP server port')
    email_destination: Optional[str] = Field(None, description='Destination email address')
    email_subject: Optional[str] = Field(None, description='Email subject line')


class TimeConfigRequest(BaseModel):
    '''Request model for configuring time monitor.'''
    enabled: bool = Field(..., description='True to enable, False to disable')
    drift_monitor_enabled: Optional[bool] = Field(None, description='Enable drift monitor')
    drift_station: Optional[str] = Field(None, description='Station callsign to sync to')
    drift_group: Optional[str] = Field(None, description='Group designator to sync to')
    drift_interval: Optional[int] = Field(None, description='Minutes between sync attempts')
    drift_threshold: Optional[float] = Field(None, description='Time drift threshold in seconds')
    drift_age: Optional[int] = Field(None, description='Maximum age of activity in minutes')
    timemaster_enabled: Optional[bool] = Field(None, description='Enable time master')
    timemaster_destination: Optional[str] = Field(None, description='Outgoing time message destination')
    timemaster_message: Optional[str] = Field(None, description='Outgoing time message text')
    timemaster_interval: Optional[int] = Field(None, description='Minutes between outgoing messages')


class StartClientRequest(BaseModel):
    '''Request model for starting pyjs8call client.'''
    headless: bool = Field(False, description='Start JS8Call in headless mode')
    debugging: bool = Field(False, description='Enable debugging')
    logging: bool = Field(False, description='Enable logging')
    args: Optional[List[str]] = Field(None, description='Additional command line arguments for JS8Call')


class StopClientRequest(BaseModel):
    '''Request model for stopping pyjs8call client.'''
    terminate_js8call: bool = Field(True, description='Whether to terminate JS8Call application')


class ScheduleEntryRequest(BaseModel):
    '''Request model for schedule operations.'''
    start_time: str = Field(..., description='Start time in HH:MM format')
    freq: Optional[int] = Field(None, description='Frequency in Hz')
    speed: Optional[str] = Field(None, description='Modem speed')
    profile: Optional[str] = Field(None, description='Profile name')
    restart: bool = Field(False, description='Restart JS8Call at this time')


class ActivityRequest(BaseModel):
    '''Request model for activity monitoring.'''
    age: Optional[int] = Field(None, description='Maximum age in seconds')
    hearing_age: Optional[int] = Field(None, description='Maximum hearing age in seconds')


class HearingRequest(BaseModel):
    '''Request model for hearing analysis.'''
    age: Optional[int] = Field(None, description='Maximum age in seconds')


class StationRequest(BaseModel):
    '''Request model for station-specific queries.'''
    callsign: str = Field(..., description='Station callsign')


class TextFieldRequest(BaseModel):
    '''Request model for setting text fields.'''
    text: str = Field(..., description='Text content to set')




class PropagationRequest(BaseModel):
    '''Request model for propagation analysis.'''
    age: Optional[int] = Field(None, description='Maximum age in minutes')
    start_time: Optional[str] = Field(None, description='Start time (ISO format)')
    end_time: Optional[str] = Field(None, description='End time (ISO format)')


class PropagationOriginRequest(BaseModel):
    '''Request model for origin-specific propagation analysis.'''
    origin: str = Field(..., description='Origin callsign')
    age: Optional[int] = Field(None, description='Maximum age in minutes')


class StatusResponse(BaseModel):
    '''Response model for status endpoints.'''
    success: bool = Field(..., description='Whether operation succeeded')
    message: Optional[str] = Field(None, description='Status message')
    data: Optional[Dict[str, Any]] = Field(None, description='Additional data')


class WebSocketEvent(BaseModel):
    '''WebSocket event model.'''
    event: str = Field(..., description='Event type')
    timestamp: float = Field(..., description='Event timestamp')
    data: Union[MessageModel, List[MessageModel], Dict[str, Any]] = Field(..., description='Event data')


class WebSocketSubscribeRequest(BaseModel):
    '''WebSocket subscription request.'''
    action: str = Field(..., description='Action to perform (subscribe/unsubscribe)')
    events: List[str] = Field(..., description='List of event types to subscribe to')


class InboxMessageModel(BaseModel):
    '''Inbox message model.'''
    origin: Optional[str] = None
    destination: Optional[str] = None
    path: Optional[str] = None
    text: Optional[str] = None
    time: Optional[str] = None
    read: Optional[bool] = None


class SpotFilterRequest(BaseModel):
    '''Request model for filtering spots.'''
    origin: Optional[str] = Field(None, description='Filter by origin callsign')
    destination: Optional[str] = Field(None, description='Filter by destination')
    grid: Optional[str] = Field(None, description='Filter by grid square')
    distance: Optional[int] = Field(None, description='Maximum distance filter')
    age: Optional[int] = Field(None, description='Maximum age in seconds')
    count: Optional[int] = Field(None, description='Limit number of results')
    profile: Optional[str] = Field(None, description='Filter by profile')
    dial_freq: Optional[int] = Field(None, description='Filter by dial frequency')  
    band: Optional[str] = Field(None, description='Filter by band')


class CallActivityResponse(BaseModel):
    '''Response model for call activity.'''
    callsign: str
    grid: Optional[str] = None
    snr: Optional[float] = None
    timestamp: Optional[float] = None
    distance: Optional[int] = None
    bearing: Optional[int] = None