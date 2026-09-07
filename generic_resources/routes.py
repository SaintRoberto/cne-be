from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import current_app, g, jsonify, request
from sqlalchemy import Date, DateTime, Integer, Numeric, Table, Time, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import jwt_required
from extensions import db
from generic_resources import generic_resources_bp
from models import utc_now


RESOURCES = [
    ("provincias", "provincias", "Provincias"),
    ("cantones", "cantones", "Cantones"),
    ("parroquias", "parroquias", "Parroquias"),
    ("evento-atencion-estados", "evento_atencion_estados", "Estados de atencion de evento"),
    ("evento-categorias", "evento_categorias", "Categorias de evento"),
    ("evento-causas", "evento_causas", "Causas de evento"),
    ("evento-clases", "evento_clases", "Clases de evento"),
    ("evento-estados", "evento_estados", "Estados de evento"),
    ("evento-fenomenos", "evento_fenomenos", "Fenomenos de evento"),
    ("evento-origenes", "evento_origenes", "Origenes de evento"),
    ("evento-subtipos", "evento_subtipos", "Subtipos de evento"),
    ("evento-tipos", "evento_tipos", "Tipos de evento"),
    ("eventos", "eventos", "Eventos"),
    ("infraestructura-tipos", "infraestructura_tipos", "Tipos de infraestructura"),
    ("infraestructuras", "infraestructuras", "Infraestructuras"),
]

AUDIT_COLUMNS = {"creador", "creacion", "modificador", "modificacion"}


def _table_cache() -> dict[str, Table]:
    return current_app.extensions.setdefault("reflected_tables", {})


def _get_table(table_name: str) -> Table:
    cache = _table_cache()
    if table_name not in cache:
        cache[table_name] = Table(
            table_name,
            db.metadata,
            autoload_with=db.engine,
            extend_existing=True,
        )
    return cache[table_name]


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items()}


def _writable_columns(table: Table) -> set[str]:
    columns = set()
    for column in table.columns:
        if column.primary_key or column.name in AUDIT_COLUMNS:
            continue
        columns.add(column.name)
    return columns


def _required_columns(table: Table) -> set[str]:
    required = set()
    for column in table.columns:
        if column.primary_key or column.nullable or column.name in AUDIT_COLUMNS:
            continue
        if column.default is not None or column.server_default is not None:
            continue
        required.add(column.name)
    return required


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("debe ser fecha/hora ISO 8601")


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("debe ser fecha ISO 8601")


def _coerce_value(column, value: Any) -> Any:
    if value is None:
        return None

    column_type = column.type
    try:
        if isinstance(column_type, Integer):
            if isinstance(value, bool):
                raise ValueError
            return int(value)
        if isinstance(column_type, Numeric):
            return Decimal(str(value))
        if isinstance(column_type, DateTime):
            return _parse_datetime(value)
        if isinstance(column_type, Date):
            return _parse_date(value)
        if isinstance(column_type, Time):
            if hasattr(value, "isoformat"):
                return value
            if isinstance(value, str):
                return datetime.strptime(value, "%H:%M:%S").time()
            raise ValueError
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{column.name}: tipo invalido") from error

    return value


def _load_payload(table: Table, *, partial: bool) -> tuple[dict[str, Any] | None, Any]:
    if not request.is_json:
        return None, (jsonify(error="Content-Type debe ser application/json"), 415)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify(error="El cuerpo debe ser un objeto JSON"), 400)

    writable = _writable_columns(table)
    unknown = sorted(set(payload) - writable)
    if unknown:
        return None, (
            jsonify(
                error="Error de validacion",
                detalles={field: ["Campo no permitido"] for field in unknown},
            ),
            400,
        )

    if partial and not payload:
        return None, (jsonify(error="Debe enviar al menos un campo"), 400)

    missing = sorted(_required_columns(table) - set(payload)) if not partial else []
    if missing:
        return None, (
            jsonify(
                error="Error de validacion",
                detalles={field: ["Campo requerido"] for field in missing},
            ),
            400,
        )

    data = {}
    errors = {}
    for field, value in payload.items():
        column = table.c[field]
        if value is None and not column.nullable:
            errors[field] = ["No puede ser nulo"]
            continue
        try:
            data[field] = _coerce_value(column, value)
        except ValueError as error:
            errors[field] = [str(error)]

    if errors:
        return None, (jsonify(error="Error de validacion", detalles=errors), 400)
    return data, None


def _with_audit_fields(data: dict[str, Any], table: Table, *, creating: bool) -> dict[str, Any]:
    values = dict(data)
    username = getattr(g.current_user, "usuario", None)
    now = utc_now()
    if creating:
        if "creador" in table.c:
            values["creador"] = username
        if "creacion" in table.c:
            values["creacion"] = now
    if "modificador" in table.c:
        values["modificador"] = username
    if "modificacion" in table.c:
        values["modificacion"] = now
    return values


def _handle_integrity_error() -> tuple[Any, int]:
    db.session.rollback()
    return jsonify(error="No se pudo completar la operacion: datos relacionados o duplicados"), 409


def _make_list(table_name: str, label: str):
    @jwt_required
    def list_items():
        table = _get_table(table_name)
        order_column = table.c.id if "id" in table.c else next(iter(table.c))
        rows = db.session.execute(select(table).order_by(order_column)).mappings().all()
        return jsonify([_row_to_dict(dict(row)) for row in rows])

    list_items.__name__ = f"list_{table_name}"
    list_items.__doc__ = f"""Listar {label}
    ---
    tags: [{label}]
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de registros
    """
    return list_items


def _make_create(table_name: str, label: str):
    @jwt_required
    def create_item():
        table = _get_table(table_name)
        data, error = _load_payload(table, partial=False)
        if error:
            return error

        values = _with_audit_fields(data, table, creating=True)
        try:
            row = db.session.execute(table.insert().values(**values).returning(table)).mappings().one()
            db.session.commit()
        except IntegrityError:
            return _handle_integrity_error()
        except SQLAlchemyError:
            db.session.rollback()
            raise

        return jsonify(_row_to_dict(dict(row))), 201

    create_item.__name__ = f"create_{table_name}"
    create_item.__doc__ = f"""Crear {label}
    ---
    tags: [{label}]
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
    responses:
      201:
        description: Registro creado
      400:
        description: Datos invalidos
      409:
        description: Datos duplicados o relacionados invalidos
    """
    return create_item


def _make_get(table_name: str, label: str):
    @jwt_required
    def get_item(item_id: int):
        table = _get_table(table_name)
        row = db.session.execute(select(table).where(table.c.id == item_id)).mappings().first()
        if row is None:
            return jsonify(error="Registro no encontrado"), 404
        return jsonify(_row_to_dict(dict(row)))

    get_item.__name__ = f"get_{table_name}"
    get_item.__doc__ = f"""Obtener {label}
    ---
    tags: [{label}]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
    responses:
      200:
        description: Registro encontrado
      404:
        description: Registro no encontrado
    """
    return get_item


def _make_update(table_name: str, label: str):
    @jwt_required
    def update_item(item_id: int):
        table = _get_table(table_name)
        exists = db.session.execute(select(table.c.id).where(table.c.id == item_id)).first()
        if exists is None:
            return jsonify(error="Registro no encontrado"), 404

        data, error = _load_payload(table, partial=True)
        if error:
            return error

        values = _with_audit_fields(data, table, creating=False)
        try:
            row = db.session.execute(
                table.update().where(table.c.id == item_id).values(**values).returning(table)
            ).mappings().one()
            db.session.commit()
        except IntegrityError:
            return _handle_integrity_error()
        except SQLAlchemyError:
            db.session.rollback()
            raise

        return jsonify(_row_to_dict(dict(row)))

    update_item.__name__ = f"update_{table_name}"
    update_item.__doc__ = f"""Actualizar {label}
    ---
    tags: [{label}]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
    responses:
      200:
        description: Registro actualizado
      404:
        description: Registro no encontrado
    """
    return update_item


def _make_delete(table_name: str, label: str):
    @jwt_required
    def delete_item(item_id: int):
        table = _get_table(table_name)
        exists = db.session.execute(select(table.c.id).where(table.c.id == item_id)).first()
        if exists is None:
            return jsonify(error="Registro no encontrado"), 404

        try:
            db.session.execute(table.delete().where(table.c.id == item_id))
            db.session.commit()
        except IntegrityError:
            return _handle_integrity_error()
        except SQLAlchemyError:
            db.session.rollback()
            raise

        return "", 204

    delete_item.__name__ = f"delete_{table_name}"
    delete_item.__doc__ = f"""Eliminar {label}
    ---
    tags: [{label}]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
    responses:
      204:
        description: Registro eliminado
      404:
        description: Registro no encontrado
      409:
        description: Registro en uso
    """
    return delete_item


for slug, table_name, label in RESOURCES:
    generic_resources_bp.add_url_rule(
        f"/{slug}",
        endpoint=f"{table_name}_list",
        view_func=_make_list(table_name, label),
        methods=["GET"],
    )
    generic_resources_bp.add_url_rule(
        f"/{slug}",
        endpoint=f"{table_name}_create",
        view_func=_make_create(table_name, label),
        methods=["POST"],
    )
    generic_resources_bp.add_url_rule(
        f"/{slug}/<int:item_id>",
        endpoint=f"{table_name}_get",
        view_func=_make_get(table_name, label),
        methods=["GET"],
    )
    generic_resources_bp.add_url_rule(
        f"/{slug}/<int:item_id>",
        endpoint=f"{table_name}_update",
        view_func=_make_update(table_name, label),
        methods=["PATCH", "PUT"],
    )
    generic_resources_bp.add_url_rule(
        f"/{slug}/<int:item_id>",
        endpoint=f"{table_name}_delete",
        view_func=_make_delete(table_name, label),
        methods=["DELETE"],
    )
