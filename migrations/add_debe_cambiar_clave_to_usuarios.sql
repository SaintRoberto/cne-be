ALTER TABLE public.usuarios
ADD COLUMN IF NOT EXISTS debe_cambiar_clave BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE public.usuarios
SET debe_cambiar_clave = TRUE
WHERE debe_cambiar_clave IS NULL;
