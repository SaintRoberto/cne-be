from datetime import datetime, timedelta, timezone
from functools import wraps
from types import SimpleNamespace

import bcrypt
import jwt
from flask import current_app, g, jsonify, request

# Passlib 1.7.4 expects metadata removed by bcrypt 4.x. Restoring only that
# read-only metadata keeps the exact requested versions interoperable.
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = SimpleNamespace(__version__=bcrypt.__version__)

from passlib.context import CryptContext

from extensions import db
from models import Usuario


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def generate_token(usuario: Usuario) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "usuario": usuario.usuario,
        "iat": now,
        "exp": now
        + timedelta(minutes=current_app.config["JWT_ACCESS_TOKEN_MINUTES"]),
    }
    return jwt.encode(
        payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256"
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None


def jwt_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "").strip()
        if not authorization:
            return jsonify(error="Se requiere el token de autorización"), 401

        parts = authorization.split()
        if len(parts) == 1:
            token = parts[0]
        elif len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            return jsonify(error="Formato de autorización inválido"), 401

        payload = decode_token(token)
        if payload is None:
            return jsonify(error="Token inválido o expirado"), 401

        try:
            usuario_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return jsonify(error="Token inválido o expirado"), 401

        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None or not usuario.activo:
            return jsonify(error="Usuario inexistente o inactivo"), 401

        g.current_user = usuario
        g.jwt_payload = payload
        return view(*args, **kwargs)

    return wrapped
