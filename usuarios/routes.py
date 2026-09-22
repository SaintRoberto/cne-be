from flask import g, jsonify
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError

from auth import generate_token, hash_password, jwt_required, verify_password
from extensions import db
from models import Usuario, utc_now
from schemas import (
    login_schema,
    register_schema,
    usuario_response_schema,
    usuario_update_schema,
    usuarios_response_schema,
)
from usuarios import usuarios_bp
from utils.validation import load_json


@usuarios_bp.post("")
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

    duplicate_conditions = [Usuario.usuario == data["usuario"]]
    if data.get("correo"):
        duplicate_conditions.append(Usuario.correo == data["correo"].lower())
    existing = db.session.scalar(
        select(Usuario).where(or_(*duplicate_conditions))
    )
    if existing:
        return jsonify(error="El usuario o correo ya está registrado"), 409

    try:
        usuario = Usuario(
            institucion_id=data["institucion_id"],
            usuario=data["usuario"],
            correo=data.get("correo").lower() if data.get("correo") else None,
            clave=hash_password(data["clave"]),
            nombres=data.get("nombres") or data.get("nombre"),
            apellidos=data.get("apellidos"),
            descripcion=data.get("descripcion"),
            celular=data.get("celular"),
            cedula=data.get("cedula"),
            aprobado=data["aprobado"],
            activo=data["activo"],
            creador=data["creador"],
            modificador=data["creador"],
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


@usuarios_bp.get("/<int:usuario_id>/datos-login")
@jwt_required
def get_datos_login(usuario_id: int):
    """Obtener datos de login por usuario
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
        description: Datos de login del usuario
      401:
        description: Token ausente o invÃ¡lido
      404:
        description: Datos de login no encontrados
    """
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        return jsonify(error="Datos de login no encontrados"), 404

    required_tables = (
        "public.usuario_perfil_coe_dpa_mesa",
        "public.perfiles",
        "public.coes",
        "public.mesas",
        "public.mesa_grupos",
        "public.emergencias",
    )
    existing_tables = set(
        db.session.execute(
            text("SELECT to_regclass(:table_name) AS table_name"),
            {"table_name": table_name},
        ).scalar()
        for table_name in required_tables
    )
    if None in existing_tables:
        return jsonify({
            "usuario_institucion_id": usuario.institucion_id,
            "usuario_login": usuario.usuario,
            "usuario_id": usuario.id,
            "usuario_descripcion": usuario.descripcion,
            "coe_id": None,
            "coe_abreviatura": None,
            "perfil_id": None,
            "perfil_nombre": None,
            "provincia_id": None,
            "provincia_nombre": None,
            "canton_id": None,
            "canton_nombre": None,
            "mesa_id": None,
            "mesa_nombre": None,
            "mesa_siglas": None,
            "mesa_grupo_id": None,
            "mesa_grupo_nombre": None,
            "emergencia_id": None,
        })

    query = text("""
        SELECT u.institucion_id AS usuario_institucion_id,
               u.usuario AS usuario_login,
               u.id AS usuario_id,
               u.descripcion AS usuario_descripcion,
               ux.coe_id,
               c.siglas AS coe_abreviatura,
               ux.perfil_id,
               pf.nombre AS perfil_nombre,
               ux.provincia_id,
               COALESCE(p.nombre, '--') AS provincia_nombre,
               ux.canton_id,
               COALESCE(k.nombre, '--') AS canton_nombre,
               ux.mesa_id,
               m.nombre AS mesa_nombre,
               m.siglas AS mesa_siglas,
               g.id AS mesa_grupo_id,
               g.nombre AS mesa_grupo_nombre,
               e.id AS emergencia_id
        FROM public.usuarios u
        INNER JOIN public.usuario_perfil_coe_dpa_mesa ux ON u.id = ux.usuario_id
        LEFT JOIN public.perfiles pf ON ux.perfil_id = pf.id
        LEFT JOIN public.coes c ON ux.coe_id = c.id
        LEFT JOIN public.provincias p ON ux.provincia_id = p.id
        LEFT JOIN public.cantones k ON ux.provincia_id = k.provincia_id AND ux.canton_id = k.id
        LEFT JOIN public.mesas m ON ux.mesa_id = m.id
        LEFT JOIN public.mesa_grupos g ON m.mesa_grupo_id = g.id
        LEFT JOIN public.emergencias e ON ux.emergencia_id = e.id
        WHERE u.id = :usuario_id
          AND COALESCE(u.activo, TRUE) = TRUE
          AND COALESCE(ux.activo, TRUE) = TRUE
        ORDER BY ux.id DESC
        LIMIT 1
    """)
    row = db.session.execute(query, {"usuario_id": usuario_id}).mappings().first()
    if row is None:
        return jsonify(error="Datos de login no encontrados"), 404

    return jsonify(dict(row))


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

    duplicate_conditions = []
    if "usuario" in data:
        duplicate_conditions.append(Usuario.usuario == data["usuario"])
    if data.get("correo"):
        duplicate_conditions.append(Usuario.correo == data["correo"].lower())
    if duplicate_conditions:
        existing = db.session.scalar(
            select(Usuario).where(
                Usuario.id != usuario_id,
                or_(*duplicate_conditions),
            )
        )
        if existing:
            return jsonify(error="El usuario o correo ya está registrado"), 409

    if "correo" in data:
        usuario.correo = data["correo"].lower() if data["correo"] else None
    if "nombre" in data and "nombres" not in data:
        data["nombres"] = data.pop("nombre")
    for field in (
        "institucion_id",
        "usuario",
        "descripcion",
        "celular",
        "nombres",
        "apellidos",
        "cedula",
        "aprobado",
        "activo",
        "modificador",
    ):
        if field in data:
            setattr(usuario, field, data[field])
    if "clave" in data:
        try:
            usuario.clave = hash_password(data["clave"])
        except ValueError as error_message:
            return jsonify(error=str(error_message)), 400
    usuario.modificador = data.get("modificador", g.current_user.usuario)
    usuario.modificacion = utc_now()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="El usuario o correo ya está registrado"), 409
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
