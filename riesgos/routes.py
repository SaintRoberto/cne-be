from flask import g, jsonify, request
from sqlalchemy import select

from auth import jwt_required
from extensions import db
from models import Riesgo
from riesgos import riesgos_bp
from schemas import riesgo_input_schema, riesgo_response_schema, riesgos_response_schema
from utils.validation import load_json


def _owned_risk(riesgo_id: int):
    return db.session.scalar(
        select(Riesgo).where(
            Riesgo.id == riesgo_id, Riesgo.propietario_id == g.current_user.id
        )
    )


@riesgos_bp.get("")
@jwt_required
def list_riesgos():
    """Listar los riesgos del usuario autenticado
    ---
    tags: [Riesgos]
    security:
      - Bearer: []
    parameters:
      - in: query
        name: estado
        type: string
        enum: [abierto, en_progreso, mitigado, cerrado]
    responses:
      200:
        description: Lista de riesgos
    """
    query = select(Riesgo).where(Riesgo.propietario_id == g.current_user.id)
    estado = request.args.get("estado")
    if estado:
        query = query.where(Riesgo.estado == estado)
    riesgos = db.session.scalars(query.order_by(Riesgo.id.desc())).all()
    return jsonify(riesgos_response_schema.dump(riesgos))


@riesgos_bp.post("")
@jwt_required
def create_riesgo():
    """Crear un riesgo
    ---
    tags: [Riesgos]
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/RiskInput'
    responses:
      201:
        description: Riesgo creado
      400:
        description: Datos inválidos
    """
    data, error = load_json(riesgo_input_schema)
    if error:
        return error
    riesgo = Riesgo(**data, propietario_id=g.current_user.id)
    db.session.add(riesgo)
    db.session.commit()
    return jsonify(riesgo_response_schema.dump(riesgo)), 201


@riesgos_bp.get("/<int:riesgo_id>")
@jwt_required
def get_riesgo(riesgo_id: int):
    """Obtener un riesgo
    ---
    tags: [Riesgos]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: riesgo_id
        type: integer
        required: true
    responses:
      200:
        description: Riesgo encontrado
      404:
        description: Riesgo no encontrado
    """
    riesgo = _owned_risk(riesgo_id)
    if riesgo is None:
        return jsonify(error="Riesgo no encontrado"), 404
    return jsonify(riesgo_response_schema.dump(riesgo))


@riesgos_bp.patch("/<int:riesgo_id>")
@riesgos_bp.put("/<int:riesgo_id>")
@jwt_required
def update_riesgo(riesgo_id: int):
    """Actualizar un riesgo
    ---
    tags: [Riesgos]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: riesgo_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/RiskInput'
    responses:
      200:
        description: Riesgo actualizado
      404:
        description: Riesgo no encontrado
    """
    riesgo = _owned_risk(riesgo_id)
    if riesgo is None:
        return jsonify(error="Riesgo no encontrado"), 404

    data, error = load_json(riesgo_input_schema, partial=True)
    if error:
        return error
    if not data:
        return jsonify(error="Debe enviar al menos un campo"), 400
    for field, value in data.items():
        setattr(riesgo, field, value)
    db.session.commit()
    return jsonify(riesgo_response_schema.dump(riesgo))


@riesgos_bp.delete("/<int:riesgo_id>")
@jwt_required
def delete_riesgo(riesgo_id: int):
    """Eliminar un riesgo
    ---
    tags: [Riesgos]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: riesgo_id
        type: integer
        required: true
    responses:
      204:
        description: Riesgo eliminado
      404:
        description: Riesgo no encontrado
    """
    riesgo = _owned_risk(riesgo_id)
    if riesgo is None:
        return jsonify(error="Riesgo no encontrado"), 404
    db.session.delete(riesgo)
    db.session.commit()
    return "", 204
