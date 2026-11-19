---
documento: Diagnósticos automáticos — informe de construcción (v1)
fecha: 2026-11-19
diseño: docs/panel/diagnosticos_v0.md (v1.0 APROBADA el 19-nov, §7 a-d tal cual)
estado: construido; pendiente del Validador antes de dejarlo activo en la diaria (§6.5)
---

# Diagnósticos v1: qué se ha construido y qué ha salido

## 1. Piezas
| pieza | fichero |
|---|---|
| disparadores (sin IA) | `src/diag/disparadores.py` |
| paquete de contexto (sin IA) | `src/diag/contexto.py` → `~/financial_archive/diag/paquetes/<fecha>/paquete.json` + gráfico |
| noticias GDELT + RSS Fed/BLS/BEA/BCE | `src/diag/noticias.py` → `~/financial_archive/diag/noticias/<fecha>.json` |
| explicador `claude -p`, cupo, seguimiento | `src/diag/explicador.py`, prompt fijo `src/diag/prompt_v1.md`, `scripts/diagnostico.sh` |
| tarjeta en «Hoy» | `src/diag/tarjeta.py` (enganchada en `src/report/panel.py`) |
| prueba en histórico | `scripts/diag_historico.py` → `docs/data/diag_historico_2022_2026-11-19.json` |
| enganche | final de `scripts/actualizar.sh`, `|| true`; `FIN_DIAG=0` lo apaga |
| tests (sin red, `claude` falso) | `tests/test_diag.py` |

## 2. Activos de referencia: sustitutos declarados
El archivo diario no tiene todos los activos de §2. Se usa el más cercano y se declara en cada paquete:
- S&P 500 → ETF **SPY**; Nasdaq → ETF **QQQ**; oro → ETF **GLD**; petróleo → futuro **CL=F** (1.er vencimiento:
  los cambios de contrato pueden dar saltos falsos).
- **Euro Stoxx 50 → ETF VGK** (bolsa europea amplia, cotiza en dólares: mezcla bolsa y euro).
- **Tesoro 10 a → FRED DGS10** (cambio en pb; llega con 1 día de retraso).
- **Dólar DXY → dólar frente al euro** (inverso del cambio de referencia del BCE, ≈ 58 % del DXY; diario). El dólar
  amplio de la Fed (DTWEXBGS) solo sale con hasta una semana de retraso: va al paquete como contexto, no dispara.
- **Bitcoin: no hay datos en el archivo ni sustituto razonable → se omite** (7 activos, no 8).

Otras decisiones de implementación (no cambian umbrales):
- Macro: la «previsión del proyecto» es la media de los 6 meses anteriores del dato **tal como se conocía el día de la
  publicación** (vintages ALFRED); σ de los errores = 1,4826 × MAD de los 120 errores anteriores (robusta: con la σ
  normal, 2020 anularía el disparador de nóminas durante años). PIB: 2 trimestres.
- Régimen: «deuda en rojo» = fase «desapalancamiento». En el histórico, el cambio mensual se fecha el 1.er día hábil del
  mes siguiente; en vivo salta el día en que cambia el clasificador diario.
- Tendencia: el lado «confirmado» es el que se mantiene ≥ 3 sesiones; una excursión de 1-2 días y la vuelta no cuentan.
- Tamaño para el tope: |σ| del disparador; tendencia y régimen cuentan 3,0.
- Primera ejecución sin estado: solo siembra lo visto (no escribe notas de días pasados).

## 3. Prueba en histórico (2022-01-03 → 2026-11-19, 256 semanas)
Umbrales aprobados, sin tocar. Enfriamiento de 5 sesiones incluido. «Solo» = días en que ese fue el único tipo.

| tipo | eventos | por semana | solo ese tipo |
|---|---|---|---|
| movimiento extremo (≥ 3 σ) | 66 | 0,26 | 42 |
| movimiento conjunto (≥ 2,5 σ en ≥ 3) | 13 | 0,05 | 1 |
| ruptura de tendencia (media 200 + 3 sesiones) | 47 | 0,18 | 45 |
| cambio de régimen | 20 | 0,08 | 18 |
| dato macro sorpresa (≥ 2 σ) | 19 | 0,07 | 17 |
| flujos fuertes (con precio ≥ 2 σ) | 52 | 0,20 | 38 |
| **eventos (días) nuevos** | **186** | **0,73** | |

- **Encaja en 0,5-3 por semana** (0,73). 117 de 256 semanas sin ningún evento; solo 1 semana con más de 3 (máximo 4);
  el tope deja 185 notas (0,72/semana). Por año: 41, 41, 37, 33, 34. 17 días más son solo actualizaciones.
- Flujos: las fuentes de Form 4/13F/recompras del archivo cubren pocos años; casi todo son alertas de volumen. 2025
  tiene más (31 de volumen) que 2022 (6).
- El 18-nov-2026 **no habría saltado**: el mayor movimiento de referencia fue el oro, −2,17 σ (< 3 σ, y solo 1 activo
  ≥ 2,5 σ). Coincide con el informe manual («grande pero no extremo»).

## 4. Ensayo del 18-nov (una nota real con `claude -p`)
Nota: `obsidian/Diagnosticos/2026-11-18_ensayo.md` (fuera de git; copia versionada en
`docs/panel/ensayos/diag_2026-11-18_ensayo.md`). Forzada (`--fecha 2026-11-18 --forzar`) porque no saltó nada.
Claude: 69 s, 4 turnos, ≈ 7 100 tokens de salida, coste equivalente estimado 0,43 $ (suscripción). Total con noticias:
3 min 14 s (GDELT respondió 429 y hubo que reintentar). Un primer intento falló sin nota (la regla de permiso de
escritura era `Write(…)`; Claude Code usa `Edit(…)`; ya corregido) y gastó lo mismo: **van 2 marcas del cupo de esta
semana**.

Frente al informe manual (`obsidian/Reports/2026-11-18_caida_oro_bolsas.md`, hecho a las 09:42 del 18-nov, con el
cierre de EE. UU. del 17; la nota usa el cierre completo del 18):

| | manual | automática |
|---|---|---|
| tamaño del oro | −2,4 % (−1,3 σ de 252 sesiones), parcial | −3,2 % (−2,17 σ de 63), cierre |
| «no extremo», no hay pánico, crédito no confirma | sí | **sí** (HY +9 pb, crédito verde, amplitud mixta 6/10) |
| oro va con la bolsa (correlación alta) | +0,40 (p85) | **+0,32 a 20 sesiones (p71)** |
| INT-11: P(pérdida oro) 57 %, mediana −3 % | sí | **sí, mismas cifras** |
| episodios parecidos y su dispersión | 53, «no permite prever» | 80 (regla distinta), mismo mensaje |
| actas del FOMC, informe de estabilidad del BCE | sí | **sí, con URL oficial** |
| caída de UnitedHealth (−10 %, −6,6 σ) | no (posterior) | **sí, como H1** (sin causa en el paquete) |
| **causa principal: tipos reales y dólar al alza (20 sesiones)** | **sí** | **no**: el paquete solo tenía el día y 5 sesiones; vio el dólar +0,19 % y el tipo real −3 pb y lo descartó. **Corregido después del ensayo:** el paquete trae ahora cambio a 20 sesiones y percentil del nivel en 1 año (dólar +2,4 % y en máximo de 1 año; tipo real p96) |
| Fed: subida descontada, Nvidia, salida a bolsa de Anthropic | sí (prensa) | **no**: GDELT solo dio 3 titulares (2 irrelevantes de mineras) |
| inventa datos o URLs | — | no: todas las URLs están en el paquete (validado automáticamente) |

Lectura: la estructura y la disciplina (datos frente a hipótesis, «ruido» como hipótesis, sin inventar) salen bien. Lo
flojo es el **contexto**: la tendencia de 20 sesiones (ya añadida) y, sobre todo, las **noticias** (GDELT es pobre y
limita mucho la frecuencia). Propuesta para el usuario: añadir una consulta GDELT por el mayor movimiento que no sea de
referencia (p. ej. «UnitedHealth») y valorar una 2.ª fuente de titulares gratuita.

## 5. Límites y riesgos
- **Notas fuera de git** (desviación de §5, que decía «las commitea la semanal»): `git status --porcelain` cuenta los
  ficheros sin seguimiento, y E1/B1/B1′ (día 3) e INT-11 (día 20) abortan con el árbol sucio. Una nota escrita entre
  semana bloquearía esos registros hasta el domingo. Se dejan en `.gitignore` (como `Actualizaciones.md`), igual que
  `research/diag/aciertos.jsonl`. Si el usuario las quiere en git, la opción segura es commitearlas en el momento
  (como `commit_informes.sh`), lo que §5 no quería: decide el usuario.
- El panel se regenera tras una nota nueva (para la tarjeta). El ensayo lo regeneró desde esta rama.
- La «previsión» macro es una tendencia propia, no el consenso de analistas (no hay consenso gratis): un «dato
  sorpresa» aquí no es lo que el mercado llama sorpresa.
- Los activos sustitutos (VGK, dólar frente al euro, CL=F) pueden dar o quitar disparadores frente al índice real.
- GDELT: 1 petición cada 5 s por IP y 429 frecuentes; con 3 reintentos, las noticias pueden tardar ~2-3 min.
- El seguimiento a 5/20 días solo mide la **dirección** de una serie elegida por Claude: coincidir no prueba la causa.
- Cada nota gasta tokens de la suscripción (≈ 1 min y ≈ 0,4 $ equivalentes en el ensayo).
