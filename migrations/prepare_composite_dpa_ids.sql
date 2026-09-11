BEGIN;

-- Los IDs geograficos son controlados por el maestro DPA, no por secuencias.
ALTER TABLE public.provincias ALTER COLUMN id DROP DEFAULT;
ALTER TABLE public.cantones ALTER COLUMN id DROP DEFAULT;
ALTER TABLE public.parroquias ALTER COLUMN id DROP DEFAULT;
ALTER TABLE public.zonas ALTER COLUMN id DROP DEFAULT;

-- El DPA de zona tiene 11 digitos y puede superar el rango de INTEGER.
ALTER TABLE public.zonas ALTER COLUMN id TYPE BIGINT;
ALTER TABLE public.provincias ALTER COLUMN dpa TYPE VARCHAR(2);
ALTER TABLE public.cantones ALTER COLUMN dpa TYPE VARCHAR(5);
ALTER TABLE public.parroquias ALTER COLUMN dpa TYPE VARCHAR(9);
ALTER TABLE public.zonas ALTER COLUMN dpa TYPE VARCHAR(11);

COMMIT;
