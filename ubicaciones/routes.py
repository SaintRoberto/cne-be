from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from flask import g, jsonify, request
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import jwt_required
from extensions import db
from models import Canton, Parroquia, Provincia, Zona
from ubicaciones import ubicaciones_bp


REQUIRED_COLUMNS = (
    "COD_PROVINCIA",
    "NOMBRE_PROVINCIA",
    "COD_CANTON",
    "NOMBRE_CANTON",
    "COD_PARROQUIA",
    "NOMBRE_PARROQUIA",
    "COD_ZONA",
    "NOMBRE_ZONA",
    "Total_Recintos",
)
MAX_IMPORT_BYTES = 5 * 1024 * 1024
CODE_WIDTHS = {
    "COD_PROVINCIA": 2,
    "COD_CANTON": 3,
    "COD_PARROQUIA": 4,
    "COD_ZONA": 2,
}


class ImportValidationError(ValueError):
    pass


def _read_csv(upload) -> list[dict[str, str]]:
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

    rows = []
    for line, row in enumerate(reader, start=2):
        if not row:
            continue
        values = {column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS}
        if not any(values.values()):
            continue
        empty = [column for column, value in values.items() if not value]
        if empty:
            raise ImportValidationError(
                f"Fila {line}: columnas sin valor: {', '.join(empty)}"
            )
        numeric = (
            "COD_PROVINCIA",
            "COD_CANTON",
            "COD_PARROQUIA",
            "COD_ZONA",
            "Total_Recintos",
        )
        invalid = [column for column in numeric if not values[column].isdigit()]
        if invalid:
            raise ImportValidationError(
                f"Fila {line}: deben ser numericos: {', '.join(invalid)}"
            )
        too_long = [
            column
            for column, width in CODE_WIDTHS.items()
            if len(values[column]) > width
        ]
        if too_long:
            raise ImportValidationError(
                f"Fila {line}: codigo excede la longitud permitida: {', '.join(too_long)}"
            )
        for column, width in CODE_WIDTHS.items():
            values[column] = values[column].zfill(width)
        rows.append(values)

    if not rows:
        raise ImportValidationError("El archivo no contiene filas para importar")
    return rows


def _unique_rows(
    rows: Iterable[dict[str, str]],
    *keys: str,
    value_keys: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, str]]:
    result = {}
    for row in rows:
        identity = tuple(row[key] for key in keys)
        existing = result.get(identity)
        if existing is not None and any(
            existing[column] != row[column] for column in value_keys
        ):
            raise ImportValidationError(
                f"Datos contradictorios para los codigos {' / '.join(identity)}"
            )
        result[identity] = row
    return result


def _composite_dpa(*codes: str) -> str:
    return "".join(codes)


def _dpa_id(dpa: str) -> int:
    return int(dpa)


def _reset_geographic_tables() -> None:
    """Vaciar solo el catalogo geografico y reiniciar sus identificadores."""
    if db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(
            text(
                "TRUNCATE TABLE public.zonas, public.parroquias, "
                "public.cantones, public.provincias RESTART IDENTITY"
            )
        )
        return

    # SQLite no implementa TRUNCATE. Este camino mantiene las pruebas y otros
    # entornos locales con el mismo comportamiento funcional.
    for model in (Zona, Parroquia, Canton, Provincia):
        db.session.execute(model.__table__.delete())

    has_sequence = db.session.execute(
        text(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'sqlite_sequence'"
        )
    ).first()
    if has_sequence:
        db.session.execute(
            text(
                "DELETE FROM sqlite_sequence "
                "WHERE name IN ('zonas', 'parroquias', 'cantones', 'provincias')"
            )
        )


@ubicaciones_bp.post("/importar")
@jwt_required
def import_locations():
    """Importar el maestro territorial DPA desde un CSV
    ---
    tags: [Ubicacion geografica]
    consumes:
      - multipart/form-data
    security:
      - Bearer: []
    parameters:
      - in: formData
        name: archivo
        type: file
        required: true
        description: CSV UTF-8 separado por punto y coma con el maestro DPA.
    responses:
      200:
        description: Catalogos reemplazados y sus identificadores reiniciados.
      400:
        description: Archivo o datos invalidos.
      409:
        description: Las tablas no se pudieron reemplazar por restricciones de integridad.
      401:
        description: Token ausente o invalido.
    """
    upload = request.files.get("archivo")
    if upload is None or not upload.filename:
        return jsonify(error="Debe adjuntar el archivo CSV en el campo 'archivo'"), 400

    try:
        rows = _read_csv(upload)
        provinces = _unique_rows(
            rows, "COD_PROVINCIA", value_keys=("NOMBRE_PROVINCIA",)
        )
        cantons = _unique_rows(
            rows,
            "COD_PROVINCIA",
            "COD_CANTON",
            value_keys=("NOMBRE_CANTON",),
        )
        parishes = _unique_rows(
            rows,
            "COD_PROVINCIA",
            "COD_CANTON",
            "COD_PARROQUIA",
            value_keys=("NOMBRE_PARROQUIA",),
        )
        zones = _unique_rows(
            rows,
            "COD_PROVINCIA",
            "COD_CANTON",
            "COD_PARROQUIA",
            "COD_ZONA",
            value_keys=("NOMBRE_ZONA",),
        )
    except ImportValidationError as error:
        return jsonify(error="Archivo CSV invalido", detalle=str(error)), 400

    username = g.current_user.usuario

    try:
        previous_counts = {
            "provincias": db.session.scalar(select(func.count(Provincia.id))),
            "cantones": db.session.scalar(select(func.count(Canton.id))),
            "parroquias": db.session.scalar(select(func.count(Parroquia.id))),
            "zonas": db.session.scalar(select(func.count(Zona.id))),
        }
        _reset_geographic_tables()

        province_by_code = {}
        for (code,), row in provinces.items():
            province_dpa = _composite_dpa(code)
            province = Provincia(
                id=_dpa_id(province_dpa),
                dpa=province_dpa,
                nombre=row["NOMBRE_PROVINCIA"],
                creador=username,
                modificador=username,
            )
            db.session.add(province)
            province_by_code[code] = province
        db.session.flush()

        canton_by_code = {}
        for (province_code, code), row in cantons.items():
            canton_dpa = _composite_dpa(province_code, code)
            canton = Canton(
                id=_dpa_id(canton_dpa),
                provincia_id=province_by_code[province_code].id,
                dpa=canton_dpa,
                nombre=row["NOMBRE_CANTON"],
                creador=username,
                modificador=username,
            )
            db.session.add(canton)
            canton_by_code[(province_code, code)] = canton
        db.session.flush()

        parish_by_code = {}
        for (province_code, canton_code, code), row in parishes.items():
            canton = canton_by_code[(province_code, canton_code)]
            parish_dpa = _composite_dpa(province_code, canton_code, code)
            parish = Parroquia(
                id=_dpa_id(parish_dpa),
                provincia_id=province_by_code[province_code].id,
                canton_id=canton.id,
                dpa=parish_dpa,
                nombre=row["NOMBRE_PARROQUIA"],
                creador=username,
                modificador=username,
            )
            db.session.add(parish)
            parish_by_code[(province_code, canton_code, code)] = parish
        db.session.flush()

        zone_records = []
        for (province_code, canton_code, parish_code, code), row in zones.items():
            parish = parish_by_code[(province_code, canton_code, parish_code)]
            zone_dpa = _composite_dpa(
                province_code, canton_code, parish_code, code
            )
            zone_records.append(
                {
                    "id": _dpa_id(zone_dpa),
                    "provincia_id": province_by_code[province_code].id,
                    "canton_id": canton_by_code[(province_code, canton_code)].id,
                    "parroquia_id": parish.id,
                    "dpa": zone_dpa,
                    "nombre": row["NOMBRE_ZONA"],
                    "creador": username,
                    "modificador": username,
                }
            )
        db.session.execute(Zona.__table__.insert(), zone_records)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                error="Importacion rechazada",
                detalle=(
                    "No se pudieron reemplazar los catalogos por una "
                    "restriccion de integridad. No se realizo ningun cambio."
                ),
            ),
            409,
        )
    except SQLAlchemyError:
        db.session.rollback()
        raise

    counters = {
        "provincias": {
            "eliminados": previous_counts["provincias"],
            "creados": len(provinces),
            "actualizados": 0,
        },
        "cantones": {
            "eliminados": previous_counts["cantones"],
            "creados": len(cantons),
            "actualizados": 0,
        },
        "parroquias": {
            "eliminados": previous_counts["parroquias"],
            "creados": len(parishes),
            "actualizados": 0,
        },
        "zonas": {
            "eliminados": previous_counts["zonas"],
            "creados": len(zones),
            "actualizados": 0,
        },
    }
    return jsonify(
        mensaje="Importacion DPA completada",
        modo="reemplazo",
        filas_procesadas=len(rows),
        **counters,
    )
