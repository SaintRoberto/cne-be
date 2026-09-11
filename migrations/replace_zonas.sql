BEGIN;

DROP TABLE IF EXISTS public.zonas;

CREATE TABLE public.zonas (
    id BIGINT PRIMARY KEY,
    provincia_id INTEGER NOT NULL REFERENCES public.provincias(id),
    canton_id INTEGER NOT NULL REFERENCES public.cantones(id),
    parroquia_id INTEGER NOT NULL REFERENCES public.parroquias(id),
    dpa VARCHAR(11) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    abreviatura VARCHAR(10),
    activo BOOLEAN DEFAULT TRUE,
    creador VARCHAR(100),
    creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificador VARCHAR(100),
    modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
