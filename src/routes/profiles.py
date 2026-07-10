import pathlib

from fastapi import (
    APIRouter,
    Depends,
    status,
    HTTPException,
    Path,
    File
)
from typing import Annotated

from schemas import ProfileResponseSchema, ProfileRequestSchema
from database import (
    get_db
)
from security.http import get_token
from config import get_jwt_auth_manager
from exceptions import TokenExpiredError, InvalidTokenError
from security.interfaces import JWTAuthManagerInterface
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.accounts import UserGroupEnum
from database.models.accounts import UserModel, UserGroupModel
from sqlalchemy.orm import selectinload

from storages.interfaces import S3StorageInterface
from config.dependencies import get_s3_storage_client

from exceptions.storage import S3FileUploadError, S3ConnectionError

from database.models.accounts import UserProfileModel

from database.models.accounts import GenderEnum

router = APIRouter()


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
        db: Annotated[AsyncSession, Depends(get_db)],
        jwt_manager: Annotated[
            JWTAuthManagerInterface,
            Depends(get_jwt_auth_manager)
        ],
        s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
        token: Annotated[str, Depends(get_token)],
        profile_info: Annotated[ProfileRequestSchema, File()],
        user_id: int = Path(gt=0)
):
    try:
        decoded_token = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )

    user = await db.scalar(
        select(UserModel)
        .options(selectinload(UserModel.profile))
        .where(UserModel.id == decoded_token["user_id"])
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    user_group = await db.get(UserGroupModel, user.group_id)

    if decoded_token["user_id"] != user_id:
        if user_group.name == UserGroupEnum.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit this profile."
            )

    if user.profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )
    avatar_suffix = pathlib.Path(profile_info.avatar.filename).suffix
    avatar_key = f"avatars/{user_id}_avatar{avatar_suffix}"
    avatar_bytes = await profile_info.avatar.read()
    try:
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=avatar_bytes
        )
    except (S3FileUploadError, S3ConnectionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )
    profile_data = profile_info.model_dump(exclude=("avatar",))
    user_profile = UserProfileModel(
        **profile_data,
        avatar=avatar_key,
        user_id=user_id
    )

    avatar_url = await s3_client.get_file_url(file_name=avatar_key)

    db.add(user_profile)
    await db.commit()
    await db.refresh(user_profile)

    return ProfileResponseSchema(
        id=user_profile.id,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name,
        gender=user_profile.gender,
        date_of_birth=user_profile.date_of_birth,
        info=user_profile.info,
        avatar=avatar_url,
        user_id=user_profile.user_id
    )
