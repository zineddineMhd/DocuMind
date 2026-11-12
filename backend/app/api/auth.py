from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core import ratelimit
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import Document, User, Workspace
from app.schemas import LoginIn, ProfileIn, RegisterIn, TokenOut, UserOut
from app.workers import indexer

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user_id=user.id, user=UserOut.model_validate(user))


def _limit(request: Request) -> None:
    ip = request.client.host if request.client else "?"
    ratelimit.check(f"auth:{ip}", get_settings().rate_limit_auth_per_min)


@router.post("/register", response_model=TokenOut, status_code=201, summary="Créer un compte")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _limit(request)
    email = body.email.lower()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise AppError(409, "Un compte existe déjà avec cette adresse e-mail.", "email_taken")
    user = User(email=email, name=body.name.strip() or email.split("@")[0], password_hash=hash_password(body.password))
    user.workspaces.append(Workspace(name="Mon espace"))  # espace par défaut pour démarrer tout de suite
    db.add(user)
    db.commit()
    return _token(user)


@router.post("/login", response_model=TokenOut, summary="Ouvrir une session")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _limit(request)
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "E-mail ou mot de passe incorrect.", "invalid_credentials")
    return _token(user)


@router.get("/me", response_model=UserOut, summary="Profil courant")
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut, summary="Modifier le profil / mot de passe")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None and body.name.strip():
        user.name = body.name.strip()
    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise AppError(400, "Mot de passe actuel incorrect.", "invalid_password")
        user.password_hash = hash_password(body.new_password)
    db.commit()
    return user


@router.delete("/me", status_code=204, summary="Supprimer le compte et toutes ses données")
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    docs = db.execute(select(Document).join(Workspace).where(Workspace.user_id == user.id)).scalars().all()
    for d in docs:
        indexer.purge_vectors(d.id)
        Path(d.storage_path).unlink(missing_ok=True)
    db.delete(user)
    db.commit()
    return Response(status_code=204)
