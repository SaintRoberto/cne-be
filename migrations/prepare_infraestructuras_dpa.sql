BEGIN;

-- zona_id referencia el ID DPA completo de zonas, que es BIGINT.
ALTER TABLE public.infraestructuras
    ALTER COLUMN zona_id TYPE BIGINT;

-- El DPA de recinto (2+3+4+2+4) identifica de forma unica la infraestructura.
ALTER TABLE public.infraestructuras
    ALTER COLUMN dpa TYPE VARCHAR(15),
    ALTER COLUMN id DROP IDENTITY IF EXISTS,
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN id TYPE BIGINT;

UPDATE public.infraestructuras
SET id = dpa::BIGINT
WHERE id IS DISTINCT FROM dpa::BIGINT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_infraestructuras_dpa
    ON public.infraestructuras (dpa);

ALTER TABLE public.infraestructuras
    DROP CONSTRAINT IF EXISTS ck_infraestructuras_id_dpa;

ALTER TABLE public.infraestructuras
    ADD CONSTRAINT ck_infraestructuras_id_dpa
    CHECK (id = dpa::BIGINT);

COMMIT;
