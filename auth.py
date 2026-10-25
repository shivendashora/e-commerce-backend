from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select

from database import AsyncSession, get_db_session
from helpers.auth.authHelpers import (
    create_access_token,
    get_current_user,
    get_user_by_username_or_email,
    hash_password,
    verify_password,
)
from model import Token, UserCreate, UserResponse
from tables import Users

router = APIRouter(prefix="/auth", tags=["auth"])


'''
    Routes
'''
@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate, session: AsyncSession = Depends(get_db_session)):

    query = select(Users).where(or_(Users.username == user.username, Users.email == user.email))
    result = await session.execute(query)
    existing = result.scalars().first()

    if existing:
        field = "Username" if existing.username == user.username else "Email"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{field} already registered"
        )

    newUser = Users(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
    )

    session.add(newUser)
    await session.commit()
    await session.refresh(newUser)

    return newUser


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_db_session),
):
    # OAuth2 spec names the field "username"; we accept either username or email in it
    user = await get_user_by_username_or_email(session, form_data.username)

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: Annotated[Users, Depends(get_current_user)]):
    return current_user
