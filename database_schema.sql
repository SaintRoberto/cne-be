CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(80) NOT NULL UNIQUE,
    correo VARCHAR(255) NOT NULL UNIQUE,
    clave VARCHAR(255) NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS riesgos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(160) NOT NULL,
    descripcion TEXT,
    probabilidad DOUBLE PRECISION NOT NULL CHECK (probabilidad BETWEEN 0 AND 1),
    impacto DOUBLE PRECISION NOT NULL CHECK (impacto BETWEEN 0 AND 1),
    estado VARCHAR(30) NOT NULL DEFAULT 'abierto'
        CHECK (estado IN ('abierto', 'en_progreso', 'mitigado', 'cerrado')),
    propietario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_usuarios_usuario ON usuarios (usuario);
CREATE INDEX IF NOT EXISTS ix_usuarios_correo ON usuarios (correo);
CREATE INDEX IF NOT EXISTS ix_riesgos_estado ON riesgos (estado);
