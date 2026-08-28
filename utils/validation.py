from flask import jsonify, request
from marshmallow import ValidationError


def load_json(schema, *, partial: bool = False):
    if not request.is_json:
        return None, (jsonify(error="Content-Type debe ser application/json"), 415)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify(error="El cuerpo debe ser un objeto JSON"), 400)

    try:
        return schema.load(data, partial=partial), None
    except ValidationError as error:
        return None, (
            jsonify(error="Error de validación", detalles=error.messages),
            400,
        )
