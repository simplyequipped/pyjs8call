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
    """Message object for API serialization."""
    
    # Core message fields
    id: Optional[str] = None
    type: Optional[str] = None
    timestamp: Optional[float] = None
    
    # Station information
    origin: Optional[str] = None
    destination: Optional[str] = None
    call: Optional[str] = None
    grid: Optional[str] = None
    
    # Message content
    text: Optional[str] = None
    value: Optional[str] = None
    cmd: Optional[str] = None
    
    # Technical details
    freq: Optional[int] = None
    dial: Optional[int] = None
    offset: Optional[int] = None
    snr: Optional[float] = None
    speed: Optional[str] = None
    tdrift: Optional[float] = None
    
    # Location/distance
    distance: Optional[int] = None
    distance_units: Optional[str] = None
    bearing: Optional[int] = None
    
    # Status/routing
    status: Optional[str] = None
    path: Optional[List[str]] = None
    profile: Optional[str] = None
    error: Optional[str] = None
    
    # Time fields
    utc: Optional[str] = None
    utc_time_str: Optional[str] = None
    local_time_str: Optional[str] = None
    
    # Complex data fields
    hearing: Optional[List[str]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    band_activity: Optional[List[Dict[str, Any]]] = None
    call_activity: Optional[List[Dict[str, Any]]] = None
    
    # Additional fields
    extra: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

    @classmethod
    def from_pyjs8call_message(cls, msg):
        """Convert pyjs8call Message object to API model.
        
        Args:
            msg: pyjs8call.message.Message object
            
        Returns:
            MessageModel: API-serializable message model
        """
        data = {}
        
        # Extract all attributes that exist on the message
        for attr in msg.attributes:
            value = getattr(msg, attr, None)
            if value is not None:
                data[attr] = value
                
        return cls(**data)


class SendMessageRequest(BaseModel):
    """Request model for sending messages."""
    destination: str = Field(..., description="Destination callsign")
    message: str = Field(..., description="Message text to send")


class SendDirectedCommandRequest(BaseModel):
    """Request model for sending directed command messages."""
    destination: str = Field(..., description="Destination callsign")
    command: str = Field(..., description="Command to send")
    message: Optional[str] = Field(None, description="Optional message text")


class SendHeartbeatRequest(BaseModel):
    """Request model for sending heartbeat."""
    grid: Optional[str] = Field(None, description="Grid square to include in heartbeat")


class SendQueryRequest(BaseModel):
    """Request model for sending query messages."""
    destination: str = Field(..., description="Destination callsign or group")


class SendAPRSGridRequest(BaseModel):
    """Request model for sending APRS grid message."""
    grid: Optional[str] = Field(None, description="Grid square to send")


class SendAPRSSMSRequest(BaseModel):
    """Request model for sending APRS SMS message."""
    phone: str = Field(..., description="Phone number")
    message: str = Field(..., description="SMS message text")


class SendAPRSEmailRequest(BaseModel):
    """Request model for sending APRS email message."""
    email: str = Field(..., description="Email address")
    message: str = Field(..., description="Email message text")


class SendAPRSPOTARequest(BaseModel):
    """Request model for sending APRS POTA spot."""
    park: str = Field(..., description="POTA park identifier")
    freq: int = Field(..., description="Frequency in Hz")
    mode: str = Field(..., description="Operating mode")
    message: str = Field(..., description="Spot message")
    callsign: Optional[str] = Field(None, description="Callsign to spot")


class SetFrequencyRequest(BaseModel):
    """Request model for setting frequency."""
    frequency: int = Field(..., description="Frequency in Hz")


class SetCallsignRequest(BaseModel):
    """Request model for setting station callsign."""
    callsign: str = Field(..., description="Station callsign")


class SetGridRequest(BaseModel):
    """Request model for setting station grid."""
    grid: str = Field(..., description="Station grid square")


class SetInfoRequest(BaseModel):
    """Request model for setting station info."""
    info: str = Field(..., description="Station info text")


class SetTXTextRequest(BaseModel):
    """Request model for setting TX text."""
    text: str = Field(..., description="Text to set in TX field")


class StatusResponse(BaseModel):
    """Response model for status endpoints."""
    success: bool = Field(..., description="Whether operation succeeded")
    message: Optional[str] = Field(None, description="Status message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")


class WebSocketEvent(BaseModel):
    """WebSocket event model."""
    event: str = Field(..., description="Event type")
    timestamp: float = Field(..., description="Event timestamp")
    data: Union[MessageModel, List[MessageModel], Dict[str, Any]] = Field(..., description="Event data")


class WebSocketSubscribeRequest(BaseModel):
    """WebSocket subscription request."""
    action: str = Field(..., description="Action to perform (subscribe/unsubscribe)")
    events: List[str] = Field(..., description="List of event types to subscribe to")


class InboxMessageModel(BaseModel):
    """Inbox message model."""
    origin: Optional[str] = None
    destination: Optional[str] = None
    path: Optional[str] = None
    text: Optional[str] = None
    time: Optional[str] = None
    read: Optional[bool] = None


class SpotFilterRequest(BaseModel):
    """Request model for filtering spots."""
    origin: Optional[str] = Field(None, description="Filter by origin callsign")
    destination: Optional[str] = Field(None, description="Filter by destination")
    grid: Optional[str] = Field(None, description="Filter by grid square")
    distance: Optional[int] = Field(0, description="Maximum distance filter")
    age: Optional[int] = Field(0, description="Maximum age in seconds")
    count: Optional[int] = Field(0, description="Limit number of results")
    profile: Optional[str] = Field(None, description="Filter by profile")
    dial_freq: Optional[int] = Field(None, description="Filter by dial frequency")
    band: Optional[str] = Field(None, description="Filter by band")


class CallActivityResponse(BaseModel):
    """Response model for call activity."""
    callsign: str
    grid: Optional[str] = None
    snr: Optional[float] = None
    timestamp: Optional[float] = None
    distance: Optional[int] = None
    bearing: Optional[int] = None