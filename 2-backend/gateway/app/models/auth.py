from pydantic import BaseModel, EmailStr, SecretStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr


class CompleteNewPasswordRequest(BaseModel):
    email: EmailStr
    new_password: SecretStr
    session: str


class EmailRequest(BaseModel):
    email: EmailStr


class PasswordTokenRequest(BaseModel):
    token: str
    new_password: SecretStr
