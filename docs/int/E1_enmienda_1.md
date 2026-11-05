# P-E1 — enmienda 1 (operativa, 2026-11-05, ANTES de registrar ninguna predicción en vivo)
**Problema:** el BIS publica el tipo oficial de BEL, DEU, ESP, FRA, ITA, NLD y PRT solo hasta 1998-12; desde 1999 su
tipo oficial es el del BCE (`bis_cbpol_xm`). Sin esto, el registro en vivo no tendría `curva` ni `d12_corto` para 7 de
16 países (en desarrollo ≤ 2004 esas filas 1999-2004 ya quedaban fuera por la misma razón, sin efecto sobre el ajuste).
**Enmienda:** en el registro en vivo, para esos 7 países, tipo corto = tipo nacional BIS hasta 1998-12 + BCE desde
1999-01 (`src/intl/e1.rasgos(..., euro_bce=True)`). Los coeficientes congelados (`research/int/e1_modelos.json`, sha256
227ffa8c…) no cambian; el ajuste ≤ 2004 no se repite. Es la definición del prerregistro (tipo oficial del país) con la
fuente que lo publica; no se ha visto ningún resultado (ninguna predicción en vivo tiene objetivo cerrado).
**Hueco aparte (sin enmienda):** CAN sin confianza empresarial OCDE desde 2026-04 → "sin dato" mientras dure.
