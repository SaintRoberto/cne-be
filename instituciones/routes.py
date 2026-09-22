from typing import Optional

from flask import g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from auth import jwt_required
from extensions import db
from instituciones import instituciones_bp
from models import Institucion, InstitucionCategoria, Usuario, utc_now
from schemas import (
    institucion_input_schema,
    institucion_response_schema,
    instituciones_response_schema,
)
from utils.validation import load_json


def _categoria_existe(categoria_id: Optional[int]) -> bool:
    return (
        categoria_id is None
        or db.session.get(InstitucionCategoria, categoria_id) is not None
    )


@instituciones_bp.get("")
@jwt_required
def list_instituciones():
    """Listar instituciones
    ---
    tags: [Instituciones]
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de instituciones
    """
    instituciones = db.session.scalars(
        select(Institucion).order_by(Institucion.id)
    ).all()
    return jsonify(instituciones_response_schema.dump(instituciones))


@instituciones_bp.post("")
@jwt_required
def create_institucion():
    """Crear una institución
    ---
    tags: [Instituciones]
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/InstitutionInput'
    responses:
      201:
        description: Institución creada
      400:
        description: Datos inválidos
      404:
        description: Categoría no encontrada
    """
    data, error = load_json(institucion_input_schema)
    if error:
        return error
    if not _categoria_existe(data.get("institucion_categoria_id")):
        return jsonify(error="Categoría de institución no encontrada"), 404

    institucion = Institucion(
        **data,
        creador=g.current_user.usuario,
        modificador=g.current_user.usuario,
    )
    db.session.add(institucion)
    db.session.commit()
    return jsonify(institucion_response_schema.dump(institucion)), 201


@instituciones_bp.get("/<int:institucion_id>")
@jwt_required
def get_institucion(institucion_id: int):
    """Obtener una institución
    ---
    tags: [Instituciones]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: institucion_id
        type: integer
        required: true
    responses:
      200:
        description: Institución encontrada
      404:
        description: Institución no encontrada
    """
    institucion = db.session.get(Institucion, institucion_id)
    if institucion is None:
        return jsonify(error="Institución no encontrada"), 404
    return jsonify(institucion_response_schema.dump(institucion))


@instituciones_bp.patch("/<int:institucion_id>")
@instituciones_bp.put("/<int:institucion_id>")
@jwt_required
def update_institucion(institucion_id: int):
    """Actualizar una institución
    ---
    tags: [Instituciones]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: institucion_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/InstitutionInput'
    responses:
      200:
        description: Institución actualizada
      404:
        description: Institución o categoría no encontrada
    """
    institucion = db.session.get(Institucion, institucion_id)
    if institucion is None:
        return jsonify(error="Institución no encontrada"), 404

    data, error = load_json(institucion_input_schema, partial=True)
    if error:
        return error
    if not data:
        return jsonify(error="Debe enviar al menos un campo"), 400
    if (
        "institucion_categoria_id" in data
        and not _categoria_existe(data["institucion_categoria_id"])
    ):
        return jsonify(error="Categoría de institución no encontrada"), 404

    for field, value in data.items():
        setattr(institucion, field, value)
    institucion.modificador = g.current_user.usuario
    institucion.modificacion = utc_now()
    db.session.commit()
    return jsonify(institucion_response_schema.dump(institucion))


@instituciones_bp.delete("/<int:institucion_id>")
@jwt_required
def delete_institucion(institucion_id: int):
    """Eliminar una institución
    ---
    tags: [Instituciones]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: institucion_id
        type: integer
        required: true
    responses:
      204:
        description: Institución eliminada
      404:
        description: Institución no encontrada
      409:
        description: La institución está en uso
    """
    institucion = db.session.get(Institucion, institucion_id)
    if institucion is None:
        return jsonify(error="Institución no encontrada"), 404

    usuario = db.session.scalar(
        select(Usuario.id).where(Usuario.institucion_id == institucion_id)
    )
    if usuario is not None:
        return jsonify(error="No se puede eliminar: la institución tiene usuarios"), 409

    db.session.delete(institucion)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="No se puede eliminar: la institución está en uso"), 409
    return "", 204
