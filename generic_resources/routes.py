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
    ("zonas", "zonas", "Zonas"),
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
DPA_WIDTHS = {
    "provincias": 2,
    "cantones": 5,
    "parroquias": 9,
    "zonas": 11,
    "infraestructuras": 15,
}

EVENT_LOOKUPS = (
    ("provincias", "provincia_id", "provincia"),
    ("cantones", "canton_id", "canton"),
    ("parroquias", "parroquia_id", "parroquia"),
    ("evento_tipos", "evento_tipo_id", "evento_tipo"),
    ("evento_subtipos", "evento_subtipo_id", "evento_subtipo"),
    ("evento_causas", "evento_causa_id", "evento_causa"),
    ("evento_origenes", "evento_origen_id", "evento_origen"),
    (
        "evento_atencion_estados",
        "evento_atencion_estado_id",
        "evento_atencion_estado",
    ),
)


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


def _normalize_dpa(table: Table, data: dict[str, Any]) -> str | None:
    width = DPA_WIDTHS.get(table.name)
    if width is None or "dpa" not in data or data["dpa"] is None:
        return None

    code = str(data["dpa"]).strip()
    if not code.isdigit() or len(code) > width:
        return f"Debe ser numerico y tener hasta {width} digitos"
    data["dpa"] = code.zfill(width)
    return None


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

    dpa_error = _normalize_dpa(table, data)
    if dpa_error:
        return None, (
            jsonify(error="Error de validacion", detalles={"dpa": [dpa_error]}),
            400,
        )
    return data, None


def _with_audit_fields(data: dict[str, Any], table: Table, *, creating: bool) -> dict[str, Any]:
    values = dict(data)
    if table.name == "infraestructuras" and "dpa" in values:
        values["id"] = int(values["dpa"])
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


def _select_events_with_relations():
    events = _get_table("eventos")
    statement = select(events)

    for table_name, foreign_key_name, response_prefix in EVENT_LOOKUPS:
        related_table = _get_table(table_name).alias(response_prefix)
        statement = statement.outerjoin(
            related_table, events.c[foreign_key_name] == related_table.c.id
        ).add_columns(
            related_table.c.nombre.label(f"{response_prefix}_nombre")
        )
       

    return events, statement


def _make_list_events_with_relations():
    @jwt_required
    def list_events_with_relations():
        events, statement = _select_events_with_relations()
        order_column = events.c.id if "id" in events.c else next(iter(events.c))
        rows = db.session.execute(statement.order_by(order_column)).mappings().all()
        return jsonify([_row_to_dict(dict(row)) for row in rows])

    list_events_with_relations.__name__ = "list_events_with_relations"
    list_events_with_relations.__doc__ = """Listar eventos con datos relacionados
    ---
    tags: [Eventos]
    security:
      - Bearer: []
    responses:
      200:
        description: Eventos con IDs, nombres y descripciones de sus catálogos relacionados
    """
    return list_events_with_relations


def _make_get_event_with_relations():
    @jwt_required
    def get_event_with_relations(item_id: int):
        events, statement = _select_events_with_relations()
        row = db.session.execute(
            statement.where(events.c.id == item_id)
        ).mappings().first()
        if row is None:
            return jsonify(error="Registro no encontrado"), 404
        return jsonify(_row_to_dict(dict(row)))

    get_event_with_relations.__name__ = "get_event_with_relations"
    get_event_with_relations.__doc__ = """Obtener un evento con datos relacionados
    ---
    tags: [Eventos]
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
    responses:
      200:
        description: Evento con IDs, nombres y descripciones de sus catálogos relacionados
      404:
        description: Evento no encontrado
    """
    return get_event_with_relations


def _make_list_by_foreign_key(
    table_name: str,
    label: str,
    foreign_key_column_name: str,
    path_parameter_name: str,
    parent_label: str,
):
    @jwt_required
    def list_items_by_parent(**path_parameters):
        """Listar registros relacionados
        ---
        tags: [Ubicacion geografica]
        security:
          - Bearer: []
        parameters:
          - in: path
            name: parent_id
            type: integer
            required: true
            description: Identificador del registro padre
        responses:
          200:
            description: Lista de registros relacionados
          401:
            description: Token ausente o invalido
        """
        table = _get_table(table_name)
        foreign_key_column = table.c.get(foreign_key_column_name)
        if foreign_key_column is None:
            current_app.logger.error(
                "%s no tiene la columna %s", table_name, foreign_key_column_name
            )
            return jsonify(
                error=f"La tabla {table_name} no tiene la columna {foreign_key_column_name}"
            ), 500

        parent_id = path_parameters[path_parameter_name]
        order_column = table.c.id if "id" in table.c else next(iter(table.c))
        rows = db.session.execute(
            select(table)
            .where(foreign_key_column == parent_id)
            .order_by(order_column)
        ).mappings().all()
        return jsonify([_row_to_dict(dict(row)) for row in rows])

    list_items_by_parent.__name__ = (
        f"list_{table_name}_by_{foreign_key_column_name}"
    )
    list_items_by_parent.__doc__ = (
        f"Listar {label} por {parent_label}\n"
        "---\n"
        "tags: [Ubicacion geografica]\n"
        "security:\n"
        "  - Bearer: []\n"
        "parameters:\n"
        "  - in: path\n"
        f"    name: {path_parameter_name}\n"
        "    type: integer\n"
        "    required: true\n"
        f"    description: Identificador de {parent_label}\n"
        "responses:\n"
        "  200:\n"
        f"    description: Lista de {label} relacionadas\n"
    )
    return list_items_by_parent


def _make_list_event_subtypes_by_type():
    @jwt_required
    def list_event_subtypes_by_type(tipo_evento_id: int):
        """Listar subtipos por tipo de evento
        ---
        tags: [Subtipos de evento]
        security:
          - Bearer: []
        parameters:
          - in: path
            name: tipo_evento_id
            type: integer
            required: true
            description: Identificador del tipo de evento seleccionado
        responses:
          200:
            description: Subtipos asociados al tipo de evento
          401:
            description: Token ausente o invalido
        """
        table = _get_table("evento_subtipos")

        # La base vigente usa evento_tipo_id. Se acepta tipo_evento_id para
        # mantener compatibilidad con esquemas que nombran la FK al revés.
        foreign_key_column = next(
            (
                table.c[column_name]
                for column_name in ("evento_tipo_id", "tipo_evento_id")
                if column_name in table.c
            ),
            None,
        )
        if foreign_key_column is None:
            current_app.logger.error(
                "evento_subtipos no tiene una FK de tipo de evento",
                extra={"columns": list(table.c.keys())},
            )
            return jsonify(error="La tabla evento_subtipos no tiene la columna de tipo de evento"), 500

        order_column = table.c.id if "id" in table.c else next(iter(table.c))
        rows = db.session.execute(
            select(table)
            .where(foreign_key_column == tipo_evento_id)
            .order_by(order_column)
        ).mappings().all()
        return jsonify([_row_to_dict(dict(row)) for row in rows])

    list_event_subtypes_by_type.__name__ = "list_event_subtypes_by_type"
    return list_event_subtypes_by_type


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
        view_func=(
            _make_list_events_with_relations()
            if table_name == "eventos"
            else _make_list(table_name, label)
        ),
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
        view_func=(
            _make_get_event_with_relations()
            if table_name == "eventos"
            else _make_get(table_name, label)
        ),
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


generic_resources_bp.add_url_rule(
    "/evento-subtipos/tipo-evento/<int:tipo_evento_id>",
    endpoint="evento_subtipos_by_tipo_evento",
    view_func=_make_list_event_subtypes_by_type(),
    methods=["GET"],
)

generic_resources_bp.add_url_rule(
    "/cantones/provincia/<int:provincia_id>",
    endpoint="cantones_by_provincia",
    view_func=_make_list_by_foreign_key(
        "cantones", "Cantones", "provincia_id", "provincia_id", "provincia"
    ),
    methods=["GET"],
)
generic_resources_bp.add_url_rule(
    "/parroquias/canton/<int:canton_id>",
    endpoint="parroquias_by_canton",
    view_func=_make_list_by_foreign_key(
        "parroquias", "Parroquias", "canton_id", "canton_id", "canton"
    ),
    methods=["GET"],
)
generic_resources_bp.add_url_rule(
    "/zonas/parroquia/<int:parroquia_id>",
    endpoint="zonas_by_parroquia",
    view_func=_make_list_by_foreign_key(
        "zonas", "Zonas", "parroquia_id", "parroquia_id", "parroquia"
    ),
    methods=["GET"],
)
