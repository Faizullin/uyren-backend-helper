from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# Code execution schemas
class CodeSubmissionRequest(BaseModel):
    code: str
    language: str
    input_data: str = ""


class CodeSubmissionResponse(BaseModel):
    execution_id: str
    status: str = "pending"
    message: str = "Code submitted for execution"


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    user_id: str
    code: str
    language: str
    input_data: str
    status: str  # pending, running, completed, error
    output: Optional[str] = None
    error_output: Optional[str] = None
    execution_time: Optional[str] = None
    memory_usage: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


# WebSocket message schemas
class WebSocketMessage(BaseModel):
    type: str  # execution_update, broadcast, error
    execution_id: Optional[str] = None
    data: dict


# Firebase user schema
class FirebaseUser(BaseModel):
    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    email_verified: bool = False


# Health check schema
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str = "Code Execution Service"
    version: str = "1.0.0"
