from flask import g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from auth import jwt_required
from extensions import db
from models import Institucion, InstitucionCategoria, utc_now
from schemas import (
    institucion_categoria_input_schema,
    institucion_categoria_response_schema,
    institucion_categorias_response_schema,
)
from institucion_categorias import institucion_categorias_bp
from utils.validation import load_json


@institucion_categorias_bp.get("")
@jwt_required
def list_institucion_categorias():
    """Listar categorías de institución
    ---
    tags: [Categorías de institución]
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de categorías
    """
    categorias = db.session.scalars(
        select(InstitucionCategoria).order_by(InstitucionCategoria.id)
    ).all()
    return jsonify(institucion_categorias_response_schema.dump(categorias))


@institucion_categorias_bp.post("")
@jwt_required
def create_institucion_categoria():
    """Crear una categoría de institución
    ---
    tags: [Categorías de institución]
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/InstitutionCategoryInput'
    responses:
      201:
        description: Categoría creada
      400:
        description: Datos inválidos
    """
    data, error = load_json(institucion_categoria_input_schema)
    if error:
        return error

    categoria = InstitucionCategoria(
        **data,
        creador=g.current_user.usuario,
        modificador=g.current_user.usuario,
    )
    db.session.add(categoria)
    db.session.commit()
    return jsonify(institucion_categoria_response_schema.dump(categoria)), 201


@institucion_categorias_bp.get("/<int:categoria_id>")
@jwt_required
def get_institucion_categoria(categoria_id: int):
    """Obtener una categoría de institución
    ---
    tags: [Categorías de institución]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: categoria_id
        type: integer
        required: true
    responses:
      200:
        description: Categoría encontrada
      404:
        description: Categoría no encontrada
    """
    categoria = db.session.get(InstitucionCategoria, categoria_id)
    if categoria is None:
        return jsonify(error="Categoría de institución no encontrada"), 404
    return jsonify(institucion_categoria_response_schema.dump(categoria))


@institucion_categorias_bp.patch("/<int:categoria_id>")
@institucion_categorias_bp.put("/<int:categoria_id>")
@jwt_required
def update_institucion_categoria(categoria_id: int):
    """Actualizar una categoría de institución
    ---
    tags: [Categorías de institución]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: categoria_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/InstitutionCategoryInput'
    responses:
      200:
        description: Categoría actualizada
      404:
        description: Categoría no encontrada
    """
    categoria = db.session.get(InstitucionCategoria, categoria_id)
    if categoria is None:
        return jsonify(error="Categoría de institución no encontrada"), 404

    data, error = load_json(institucion_categoria_input_schema, partial=True)
    if error:
        return error
    if not data:
        return jsonify(error="Debe enviar al menos un campo"), 400

    for field, value in data.items():
        setattr(categoria, field, value)
    categoria.modificador = g.current_user.usuario
    categoria.modificacion = utc_now()
    db.session.commit()
    return jsonify(institucion_categoria_response_schema.dump(categoria))


@institucion_categorias_bp.delete("/<int:categoria_id>")
@jwt_required
def delete_institucion_categoria(categoria_id: int):
    """Eliminar una categoría de institución
    ---
    tags: [Categorías de institución]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: categoria_id
        type: integer
        required: true
    responses:
      204:
        description: Categoría eliminada
      404:
        description: Categoría no encontrada
      409:
        description: La categoría está en uso
    """
    categoria = db.session.get(InstitucionCategoria, categoria_id)
    if categoria is None:
        return jsonify(error="Categoría de institución no encontrada"), 404

    institucion = db.session.scalar(
        select(Institucion.id).where(
            Institucion.institucion_categoria_id == categoria_id
        )
    )
    if institucion is not None:
        return jsonify(error="No se puede eliminar: la categoría tiene instituciones"), 409

    db.session.delete(categoria)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="No se puede eliminar: la categoría está en uso"), 409
    return "", 204
