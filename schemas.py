from marshmallow import Schema, fields, validate


EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class RegisterSchema(Schema):
    institucion_id = fields.Integer(required=True, strict=True)
    usuario = fields.String(required=True, validate=validate.Length(min=3, max=100))
    correo = fields.String(
        allow_none=True,
        validate=[validate.Length(max=150), validate.Regexp(EMAIL_PATTERN)],
    )
    clave = fields.String(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )
    nombres = fields.String(allow_none=True, validate=validate.Length(max=100))
    apellidos = fields.String(allow_none=True, validate=validate.Length(max=100))
    nombre = fields.String(
        load_only=True, allow_none=True, validate=validate.Length(max=200)
    )
    descripcion = fields.String(allow_none=True)
    celular = fields.String(allow_none=True, validate=validate.Length(max=20))
    cedula = fields.String(allow_none=True, validate=validate.Length(max=20))
    aprobado = fields.Boolean(load_default=False)
    activo = fields.Boolean(load_default=True)
    creador = fields.String(load_default="Sistema", validate=validate.Length(max=100))


class LoginSchema(Schema):
    usuario = fields.String(required=True)
    clave = fields.String(required=True, load_only=True)


class UsuarioUpdateSchema(Schema):
    institucion_id = fields.Integer(strict=True)
    usuario = fields.String(validate=validate.Length(min=3, max=100))
    correo = fields.String(
        allow_none=True,
        validate=[validate.Length(max=150), validate.Regexp(EMAIL_PATTERN)],
    )
    clave = fields.String(load_only=True, validate=validate.Length(min=8, max=128))
    nombres = fields.String(allow_none=True, validate=validate.Length(max=100))
    apellidos = fields.String(allow_none=True, validate=validate.Length(max=100))
    nombre = fields.String(
        load_only=True, allow_none=True, validate=validate.Length(max=200)
    )
    descripcion = fields.String(allow_none=True)
    celular = fields.String(allow_none=True, validate=validate.Length(max=20))
    cedula = fields.String(allow_none=True, validate=validate.Length(max=20))
    aprobado = fields.Boolean()
    activo = fields.Boolean()
    modificador = fields.String(validate=validate.Length(max=100))


class UsuarioResponseSchema(Schema):
    id = fields.Integer(dump_only=True)
    institucion_id = fields.Integer(dump_only=True)
    usuario = fields.String(dump_only=True)
    correo = fields.String(dump_only=True)
    descripcion = fields.String(dump_only=True, allow_none=True)
    celular = fields.String(dump_only=True, allow_none=True)
    nombres = fields.String(dump_only=True, allow_none=True)
    apellidos = fields.String(dump_only=True, allow_none=True)
    nombre_completo = fields.String(dump_only=True)
    cedula = fields.String(dump_only=True, allow_none=True)
    aprobado = fields.Boolean(dump_only=True, allow_none=True)
    activo = fields.Boolean(dump_only=True)
    creador = fields.String(dump_only=True, allow_none=True)
    creacion = fields.DateTime(dump_only=True, allow_none=True)
    modificador = fields.String(dump_only=True, allow_none=True)
    modificacion = fields.DateTime(dump_only=True, allow_none=True)


class InstitucionCategoriaInputSchema(Schema):
    nombre = fields.String(required=True, validate=validate.Length(min=1, max=100))
    descripcion = fields.String(allow_none=True)
    activo = fields.Boolean(load_default=True)


class InstitucionCategoriaResponseSchema(Schema):
    id = fields.Integer(dump_only=True)
    nombre = fields.String(dump_only=True)
    descripcion = fields.String(dump_only=True, allow_none=True)
    activo = fields.Boolean(dump_only=True, allow_none=True)
    creador = fields.String(dump_only=True, allow_none=True)
    creacion = fields.DateTime(dump_only=True, allow_none=True)
    modificador = fields.String(dump_only=True, allow_none=True)
    modificacion = fields.DateTime(dump_only=True, allow_none=True)


class InstitucionInputSchema(Schema):
    institucion_categoria_id = fields.Integer(allow_none=True, strict=True)
    nombre = fields.String(required=True, validate=validate.Length(min=1, max=200))
    siglas = fields.String(allow_none=True, validate=validate.Length(max=50))
    observaciones = fields.String(allow_none=True)
    activo = fields.Boolean(load_default=True)


class InstitucionResponseSchema(Schema):
    id = fields.Integer(dump_only=True)
    institucion_categoria_id = fields.Integer(dump_only=True, allow_none=True)
    nombre = fields.String(dump_only=True)
    siglas = fields.String(dump_only=True, allow_none=True)
    observaciones = fields.String(dump_only=True, allow_none=True)
    activo = fields.Boolean(dump_only=True, allow_none=True)
    creador = fields.String(dump_only=True, allow_none=True)
    creacion = fields.DateTime(dump_only=True, allow_none=True)
    modificador = fields.String(dump_only=True, allow_none=True)
    modificacion = fields.DateTime(dump_only=True, allow_none=True)


register_schema = RegisterSchema()
login_schema = LoginSchema()
usuario_update_schema = UsuarioUpdateSchema()
usuario_response_schema = UsuarioResponseSchema()
usuarios_response_schema = UsuarioResponseSchema(many=True)
institucion_categoria_input_schema = InstitucionCategoriaInputSchema()
institucion_categoria_response_schema = InstitucionCategoriaResponseSchema()
institucion_categorias_response_schema = InstitucionCategoriaResponseSchema(many=True)
institucion_input_schema = InstitucionInputSchema()
institucion_response_schema = InstitucionResponseSchema()
instituciones_response_schema = InstitucionResponseSchema(many=True)
