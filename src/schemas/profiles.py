from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl

from database.models.accounts import GenderEnum
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: UploadFile

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_first_name(cls, value: str):
        validate_name(value)
        return value.lower()

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: GenderEnum):
        validate_gender(value)
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: UploadFile):
        validate_image(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date):
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value):
        if not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str
    user_id: int
