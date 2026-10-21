from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation

from flask import g, jsonify, request
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import jwt_required
from extensions import db
from infraestructuras import infraestructuras_bp
from models import Canton, Infraestructura, InfraestructuraTipo, Parroquia, Provincia, Zona, utc_now


MAX_IMPORT_BYTES = 5 * 1024 * 1024
REQUIRED_COLUMNS = (
    "CODIGO PROVINCIA",
    "CODIGO CANTON",
    "CODIGO PARROQUIA",
    "CODIGO ZONA",
    "CODIGO RECINTO",
    "NOMBRE RECINTO",
    "DIRECCION RECINTO",
    "long",
    "lat",
)
CODE_WIDTHS = {
    "CODIGO PROVINCIA": 2,
    "CODIGO CANTON": 3,
    "CODIGO PARROQUIA": 4,
    "CODIGO ZONA": 2,
    "CODIGO RECINTO": 4,
}


class ImportValidationError(ValueError):
    pass


class MissingGeographyError(ValueError):
    pass


def _missing_table_columns(table_name: str, required_columns: tuple[str, ...]) -> list[str]:
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return ["Tabla no encontrada"]

    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    return [
        column_name
        for column_name in required_columns
        if column_name not in existing_columns
    ]


def _optional_infrastructure_column(
    column_names: set[str],
    column_name: str,
) -> str:
    if column_name in column_names:
        return f"i.{column_name}"
    return f"NULL AS {column_name}"


def _optional_joined_column(
    table_alias: str,
    column_names: set[str],
    column_name: str,
    label: str,
) -> str:
    if column_name in column_names:
        return f"{table_alias}.{column_name} AS {label}"
    return f"NULL AS {label}"


def _float_or_none(value):
    return float(value) if value is not None else None


def _infrastructure_list_item(item: Infraestructura) -> dict[str, object]:
    return {
        "id": item.id,
        "provincia_id": item.provincia_id,
        "canton_id": item.canton_id,
        "parroquia_id": item.parroquia_id,
        "zona_id": item.zona_id,
        "dpa": item.dpa,
        "infraestructura_tipo_id": item.infraestructura_tipo_id,
        "nombre": item.nombre,
        "direccion": item.direccion,
        "longitud": _float_or_none(item.longitud),
        "latitud": _float_or_none(item.latitud),
        "activo": item.activo,
    }


def _decimal(value: str, column: str, line: int) -> Decimal:
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return Decimal("0")
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ImportValidationError(
            f"Fila {line}: {column} debe ser un numero valido"
        ) from error


def _read_csv(upload) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    content = upload.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise ImportValidationError("El archivo supera el limite de 5 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportValidationError("El archivo debe estar codificado en UTF-8") from error

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    headers = tuple(reader.fieldnames or ())
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise ImportValidationError(
            f"Faltan columnas requeridas: {', '.join(missing)}"
        )

    records: dict[str, dict[str, object]] = {}
    coordinate_issues: list[dict[str, object]] = []
    for line, source in enumerate(reader, start=2):
        if not source or not any((value or "").strip() for value in source.values()):
            continue
        values = {column: (source.get(column) or "").strip() for column in REQUIRED_COLUMNS}
        required_values = [column for column in REQUIRED_COLUMNS if column not in {"DIRECCION RECINTO", "long", "lat"}]
        empty = [column for column in required_values if not values[column]]
        if empty:
            raise ImportValidationError(
                f"Fila {line}: columnas sin valor: {', '.join(empty)}"
            )

        for column, width in CODE_WIDTHS.items():
            code = values[column]
            if not code.isdigit() or len(code) > width:
                raise ImportValidationError(
                    f"Fila {line}: {column} debe ser numerico y tener hasta {width} digitos"
                )
            values[column] = code.zfill(width)

        province_dpa = values["CODIGO PROVINCIA"]
        canton_dpa = f"{province_dpa}{values['CODIGO CANTON']}"
        parish_dpa = f"{canton_dpa}{values['CODIGO PARROQUIA']}"
        zone_dpa = f"{parish_dpa}{values['CODIGO ZONA']}"
        infrastructure_dpa = f"{zone_dpa}{values['CODIGO RECINTO']}"
        longitude = _decimal(values["long"], "long", line)
        latitude = _decimal(values["lat"], "lat", line)
        longitude_out_of_range = not Decimal("-180") <= longitude <= Decimal("180")
        latitude_out_of_range = not Decimal("-90") <= latitude <= Decimal("90")
        if longitude_out_of_range or latitude_out_of_range:
            coordinate_issues.append(
                {
                    "fila": line,
                    "dpa": infrastructure_dpa,
                    "nombre": values["NOMBRE RECINTO"],
                    "longitud_original": values["long"],
                    "latitud_original": values["lat"],
                    "longitud_asignada": 0.0,
                    "latitud_asignada": 0.0,
                    "mensaje": "Coordenada incorrecta, corregir y volver a cargar el archivo",
                }
            )
            longitude = Decimal("0")
            latitude = Decimal("0")

        record = {
            "id": int(infrastructure_dpa),
            "provincia_id": int(province_dpa),
            "canton_id": int(canton_dpa),
            "parroquia_id": int(parish_dpa),
            "zona_id": int(zone_dpa),
            "dpa": infrastructure_dpa,
            "nombre": values["NOMBRE RECINTO"],
            "direccion": values["DIRECCION RECINTO"] or None,
            "longitud": longitude,
            "latitud": latitude,
            "activo": True,
        }
        previous = records.get(infrastructure_dpa)
        if previous is not None and previous != record:
            raise ImportValidationError(
                f"Datos contradictorios para el recinto DPA {infrastructure_dpa}"
            )
        records[infrastructure_dpa] = record

    if not records:
        raise ImportValidationError("El archivo no contiene filas para importar")
    return list(records.values()), coordinate_issues


def _validate_geography(records: list[dict[str, object]]) -> None:
    checks = (
        (Provincia, "provincia_id", "provincia"),
        (Canton, "canton_id", "canton"),
        (Parroquia, "parroquia_id", "parroquia"),
        (Zona, "zona_id", "zona"),
    )
    for model, field, label in checks:
        expected = {int(record[field]) for record in records}
        existing = set(
            db.session.scalars(select(model.id).where(model.id.in_(expected))).all()
        )
        missing = sorted(expected - existing)
        if missing:
            sample = ", ".join(str(value) for value in missing[:10])
            suffix = "..." if len(missing) > 10 else ""
            raise MissingGeographyError(
                f"No existen {len(missing)} codigos de {label}: {sample}{suffix}"
            )


@infraestructuras_bp.get(
    "/infraestructura_tipo/<int:infraestructura_tipo_id>"
)
@jwt_required
def get_infrastructures_by_type(infraestructura_tipo_id: int):
    """Obtener infraestructuras por tipo
    ---
    tags: [Infraestructuras]
    security:
      - Bearer: []
    parameters:
      - name: infraestructura_tipo_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Lista de infraestructuras del tipo seleccionado
    """
    items = db.session.scalars(
        select(Infraestructura)
        .where(Infraestructura.infraestructura_tipo_id == infraestructura_tipo_id)
        .order_by(Infraestructura.id)
    ).all()
    return jsonify([_infrastructure_list_item(item) for item in items])


@infraestructuras_bp.get(
    "/parroquia/<int:parroquia_id>/infraestructura_tipo/"
    "<int:infraestructura_tipo_id>"
)
@jwt_required
def get_infrastructures_by_parish_and_type(
    parroquia_id: int,
    infraestructura_tipo_id: int,
):
    """Obtener infraestructuras por parroquia y tipo
    ---
    tags: [Infraestructuras]
    security:
      - Bearer: []
    parameters:
      - name: parroquia_id
        in: path
        type: integer
        required: true
      - name: infraestructura_tipo_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Lista de infraestructuras por parroquia y tipo
        schema:
          type: array
          items:
            type: object
            properties:
              id: {type: integer}
              nombre: {type: string}
              direccion: {type: string}
              tipologia: {type: string}
              institucion: {type: string}
              longitud: {type: number}
              latitud: {type: number}
      401:
        description: Token ausente o invalido
      500:
        description: Esquema incompleto
    """
    required_columns = {
        "infraestructuras": (
            "id",
            "nombre",
            "direccion",
            "longitud",
            "latitud",
            "parroquia_id",
            "infraestructura_tipo_id",
        ),
        "infraestructura_tipos": ("id", "nombre"),
    }
    missing = {
        table_name: columns
        for table_name, columns in (
            (table_name, _missing_table_columns(table_name, columns))
            for table_name, columns in required_columns.items()
        )
        if columns
    }
    if missing:
        return jsonify(error="Esquema incompleto", detalles=missing), 500

    inspector = inspect(db.engine)
    infrastructure_columns = {
        column["name"] for column in inspector.get_columns("infraestructuras")
    }
    infrastructure_type_columns = {
        column["name"] for column in inspector.get_columns("infraestructura_tipos")
    }
    tipologia_column = _optional_joined_column(
        "it", infrastructure_type_columns, "nombre", "tipologia"
    )
    institucion_column = _optional_infrastructure_column(
        infrastructure_columns, "institucion"
    )
    query = db.text(
        f"""
        SELECT
            i.id,
            i.nombre,
            i.direccion,
            {tipologia_column},
            {institucion_column},
            i.longitud,
            i.latitud
        FROM infraestructuras i
        INNER JOIN infraestructura_tipos it
            ON it.id = i.infraestructura_tipo_id
        WHERE i.parroquia_id = :parroquia_id
          AND i.infraestructura_tipo_id = :infraestructura_tipo_id
        ORDER BY i.id
        """
    )
    rows = db.session.execute(
        query,
        {
            "parroquia_id": parroquia_id,
            "infraestructura_tipo_id": infraestructura_tipo_id,
        },
    ).mappings().all()

    return jsonify(
        [
            {
                "id": row["id"],
                "nombre": row["nombre"],
                "direccion": row["direccion"],
                "tipologia": row["tipologia"],
                "institucion": row["institucion"],
                "longitud": _float_or_none(row["longitud"]),
                "latitud": _float_or_none(row["latitud"]),
            }
            for row in rows
        ]
    )


@infraestructuras_bp.post("/importar")
@jwt_required
def import_infrastructures():
    """Importar recintos electorales desde CSV
    ---
    tags: [Infraestructuras]
    consumes:
      - multipart/form-data
    security:
      - Bearer: []
    parameters:
      - in: formData
        name: infraestructura_tipo_id
        type: integer
        required: true
        description: Tipo asignado a las infraestructuras importadas.
      - in: formData
        name: archivo
        type: file
        required: true
        description: CSV UTF-8 separado por punto y coma.
    responses:
      200:
        description: Recintos creados o actualizados por DPA.
      400:
        description: Archivo invalido.
      409:
        description: El archivo referencia codigos geograficos inexistentes.
    """
    raw_infrastructure_type_id = (
        request.form.get("infraestructura_tipo_id") or ""
    ).strip()
    try:
        infrastructure_type_id = int(raw_infrastructure_type_id)
    except (TypeError, ValueError):
        return jsonify(error="Debe seleccionar un tipo de infraestructura valido"), 400
    if (
        infrastructure_type_id <= 0
        or db.session.get(InfraestructuraTipo, infrastructure_type_id) is None
    ):
        return jsonify(error="El tipo de infraestructura seleccionado no existe"), 400

    upload = request.files.get("archivo")
    if upload is None or not upload.filename:
        return jsonify(error="Debe adjuntar el archivo CSV en el campo 'archivo'"), 400
    if not upload.filename.lower().endswith(".csv"):
        return jsonify(error="El archivo debe tener extension .csv"), 400

    try:
        records, coordinate_issues = _read_csv(upload)
        for record in records:
            record["infraestructura_tipo_id"] = infrastructure_type_id
        _validate_geography(records)
    except ImportValidationError as error:
        return jsonify(error="Archivo CSV invalido", detalle=str(error)), 400
    except MissingGeographyError as error:
        return jsonify(error="Importacion rechazada", detalle=str(error)), 409

    counters = {"creados": 0, "actualizados": 0, "sin_cambios": 0}
    username = g.current_user.usuario
    try:
        existing_by_dpa = {
            item.dpa: item
            for item in db.session.scalars(
                select(Infraestructura).where(
                    Infraestructura.dpa.in_([record["dpa"] for record in records])
                )
            ).all()
        }
        for record in records:
            instance = existing_by_dpa.get(record["dpa"])
            if instance is None:
                db.session.add(
                    Infraestructura(
                        **record,
                        creador=username,
                        modificador=username,
                    )
                )
                counters["creados"] += 1
                continue

            changes = {
                key: value
                for key, value in record.items()
                if getattr(instance, key) != value
            }
            if not changes:
                counters["sin_cambios"] += 1
                continue
            for key, value in changes.items():
                setattr(instance, key, value)
            instance.modificador = username
            instance.modificacion = utc_now()
            counters["actualizados"] += 1
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                error="Importacion rechazada",
                detalle="No se realizo ningun cambio por una restriccion de integridad.",
            ),
            409,
        )
    except SQLAlchemyError:
        db.session.rollback()
        raise

    return jsonify(
        mensaje=(
            "Importacion completada con coordenadas incorrectas. Corrija el archivo y vuelva a cargarlo."
            if coordinate_issues
            else "Importacion de infraestructuras completada"
        ),
        infraestructura_tipo_id=infrastructure_type_id,
        filas_procesadas=len(records),
        coordenadas_corregidas=coordinate_issues,
        **counters,
    )
