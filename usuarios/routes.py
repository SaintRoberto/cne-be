from flask import g, jsonify
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from auth import generate_token, hash_password, jwt_required, verify_password
from extensions import db
from models import Usuario
from schemas import (
    login_schema,
    register_schema,
    usuario_response_schema,
    usuario_update_schema,
    usuarios_response_schema,
)
from usuarios import usuarios_bp
from utils.validation import load_json


@usuarios_bp.post("/register")
def register():
    """Registrar un usuario
    ---
    tags: [Autenticación]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/RegisterInput'
    responses:
      201:
        description: Usuario registrado y token emitido
      400:
        description: Datos inválidos
      409:
        description: Usuario o correo ya existe
    """
    data, error = load_json(register_schema)
    if error:
        return error

    existing = db.session.scalar(
        select(Usuario).where(
            or_(Usuario.usuario == data["usuario"], Usuario.correo == data["correo"])
        )
    )
    if existing:
        return jsonify(error="El usuario o correo ya está registrado"), 409

    try:
        usuario = Usuario(
            usuario=data["usuario"],
            correo=data["correo"].lower(),
            clave=hash_password(data["clave"]),
            nombre=data["nombre"],
        )
    except ValueError as error_message:
        return jsonify(error=str(error_message)), 400

    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="El usuario o correo ya está registrado"), 409

    return (
        jsonify(
            token=generate_token(usuario),
            tipo="Bearer",
            usuario=usuario_response_schema.dump(usuario),
        ),
        201,
    )


@usuarios_bp.post("/login")
def login():
    """Iniciar sesión
    ---
    tags: [Autenticación]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/LoginInput'
    responses:
      200:
        description: Token JWT
      401:
        description: Credenciales inválidas
    """
    data, error = load_json(login_schema)
    if error:
        return error

    usuario = db.session.scalar(
        select(Usuario).where(Usuario.usuario == data["usuario"])
    )
    if (
        usuario is None
        or not usuario.activo
        or not verify_password(data["clave"], usuario.clave)
    ):
        return jsonify(error="Credenciales inválidas"), 401

    return jsonify(
        token=generate_token(usuario),
        tipo="Bearer",
        usuario=usuario_response_schema.dump(usuario),
    )


@usuarios_bp.get("/me")
@jwt_required
def me():
    """Obtener el usuario autenticado
    ---
    tags: [Usuarios]
    security:
      - Bearer: []
    responses:
      200:
        description: Usuario autenticado
      401:
        description: Token ausente o inválido
    """
    return jsonify(usuario_response_schema.dump(g.current_user))


@usuarios_bp.get("")
@jwt_required
def list_usuarios():
    """Listar usuarios
    ---
    tags: [Usuarios]
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de usuarios sin contraseñas
    """
    usuarios = db.session.scalars(select(Usuario).order_by(Usuario.id)).all()
    return jsonify(usuarios_response_schema.dump(usuarios))


@usuarios_bp.get("/<int:usuario_id>")
@jwt_required
def get_usuario(usuario_id: int):
    """Obtener un usuario
    ---
    tags: [Usuarios]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: usuario_id
        type: integer
        required: true
    responses:
      200:
        description: Usuario encontrado
      404:
        description: Usuario no encontrado
    """
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        return jsonify(error="Usuario no encontrado"), 404
    return jsonify(usuario_response_schema.dump(usuario))


@usuarios_bp.patch("/<int:usuario_id>")
@usuarios_bp.put("/<int:usuario_id>")
@jwt_required
def update_usuario(usuario_id: int):
    """Actualizar un usuario
    ---
    tags: [Usuarios]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: usuario_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/UserUpdateInput'
    responses:
      200:
        description: Usuario actualizado
      404:
        description: Usuario no encontrado
    """
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        return jsonify(error="Usuario no encontrado"), 404

    data, error = load_json(usuario_update_schema, partial=True)
    if error:
        return error
    if not data:
        return jsonify(error="Debe enviar al menos un campo"), 400

    if "correo" in data:
        usuario.correo = data["correo"].lower()
    if "nombre" in data:
        usuario.nombre = data["nombre"]
    if "activo" in data:
        usuario.activo = data["activo"]
    if "clave" in data:
        try:
            usuario.clave = hash_password(data["clave"])
        except ValueError as error_message:
            return jsonify(error=str(error_message)), 400

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="El correo ya está registrado"), 409
    return jsonify(usuario_response_schema.dump(usuario))


@usuarios_bp.delete("/<int:usuario_id>")
@jwt_required
def delete_usuario(usuario_id: int):
    """Eliminar un usuario
    ---
    tags: [Usuarios]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: usuario_id
        type: integer
        required: true
    responses:
      204:
        description: Usuario eliminado
      404:
        description: Usuario no encontrado
    """
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        return jsonify(error="Usuario no encontrado"), 404
    db.session.delete(usuario)
    db.session.commit()
    return "", 204
