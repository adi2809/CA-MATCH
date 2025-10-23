from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..core.security import create_access_token, get_password_hash, verify_password
from ..database import get_db
from ..dependencies import get_current_user
from ..models import StudentProfile, User, UserRole
from ..schemas import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter((User.email == user_in.email) | (User.uni == user_in.uni)).first():
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        email=user_in.email,
        uni=user_in.uni,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    db.flush()

    if user.role == UserRole.STUDENT:
        profile = StudentProfile(user_id=user.id)
        db.add(profile)

    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    user = db.query(User).filter(User.uni == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect UNI or password")
    access_token = create_access_token(data={"sub": user.uni, "role": user.role})
    return Token(access_token=access_token, role=user.role)



@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

