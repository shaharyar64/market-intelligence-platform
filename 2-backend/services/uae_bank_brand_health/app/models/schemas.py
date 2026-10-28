from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class UserStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    FORCE_CHANGE_PASSWORD = "FORCE_CHANGE_PASSWORD"

class CreateUserRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    temporary_password: str = Field(..., min_length=8, description="Temporary password")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    name: str = Field(..., description="Full name of the user")  # NEW

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "email": "user@example.com",
                "temporary_password": "TempPass123!",
                "role": "user",
                "name": "John Doe"
            }]
        }
    }

class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = Field(None, description="New email address")
    role: Optional[UserRole] = Field(None, description="New role")
    enabled: Optional[bool] = Field(None, description="Enable/disable user")
    name: Optional[str] = Field(None, description="Full name of the user")  # NEW

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "email": "newemail@example.com",
                "role": "admin",
                "enabled": True,
                "name": "Jane Smith"
            }]
        }
    }

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class SetPasswordRequest(BaseModel):
    email: EmailStr
    session: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    role: str
    password_updated: bool

class NewPasswordRequiredResponse(BaseModel):
    challenge_name: str = "NEW_PASSWORD_REQUIRED"
    session: str
    message: str = "New password required. Please set a new password."
    password_updated: bool = False

class UserResponse(BaseModel):
    sub: str
    email: str
    email_verified: bool = True
    role: str
    enabled: bool = True
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None  # NEW

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int

class CreateUserResponse(BaseModel):
    message: str
    username: str
    role: str
    status: str
    name: str  # NEW

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "message": "User created successfully",
                "username": "user@example.com",
                "role": "user",
                "status": "FORCE_CHANGE_PASSWORD",
                "name": "John Doe"
            }]
        }
    }

class MessageResponse(BaseModel):
    message: str
