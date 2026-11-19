---
documento: Diagnósticos automáticos («¿por qué ha pasado esto?») — diseño
version: 1.0 APROBADA (2026-11-19)
estado: aprobado tal cual el 19-nov (§7 a-d); en construcción (src/diag/). Los umbrales de §2 se fijan ANTES de mirar qué eventos dispararían (como alertas v1).
---

# Diagnósticos: buscar la causa cuando pasa algo fuerte

## 0. Qué es y qué no es
- Cuando salta un **disparador** (§2), el sistema reúne el **contexto** del día (§3) y Claude, en modo automático,
  escribe una **nota de diagnóstico** (§4): hipótesis de causa ordenadas, evidencia a favor y en contra, confianza y
  qué dato la confirmaría o la descartaría. Es la versión automática del informe del 18-nov
  (`obsidian/Reports/2026-11-18_caida_oro_bolsas.md`), con la misma estructura.
- **Descriptivo.** No es una señal de cartera, no cambia B0/B1/B1′, no entra en ningún modelo, no da órdenes a Alpaca.
  Una explicación posterior («ex post») siempre suena convincente: la nota lo dice arriba y separa **datos** (hechos
  medidos) de **hipótesis** (lo que Claude infiere).
- Coste: cada nota gasta tokens de la suscripción del usuario → tope semanal (§5).

## 1. Piezas
| pieza | dónde | qué hace |
|---|---|---|
| disparadores | `src/diag/disparadores.py` (nuevo) | lee lo que la diaria ya descarga y devuelve eventos nuevos con su medida |
| contexto | `src/diag/contexto.py` (nuevo) | arma un paquete JSON + gráficos del día del evento (sin IA) |
| explicador | `scripts/diagnostico.sh` (nuevo) | `claude -p` con un prompt fijo, herramientas limitadas y el paquete; escribe la nota |
| salida | `obsidian/Diagnosticos/AAAA-MM-DD_<evento>.md` + tarjeta en «Hoy» del panel + aviso de macOS | |
| enganche | final de `scripts/actualizar.sh` (diaria), `|| true` | nunca afecta a la diaria |

## 2. Disparadores (umbrales propuestos, a aprobar)
1. **Movimiento extremo** en un activo de referencia (S&P 500, Nasdaq, Euro Stoxx 50, oro, Tesoro 10 a, dólar DXY,
   petróleo, bitcoin): |rentabilidad del día| ≥ **3 σ** (σ de las 63 sesiones anteriores), o **2,5 σ** en ≥ 3 de ellos
   el mismo día (movimiento conjunto).
2. **Ruptura de tendencia**: el S&P 500, el oro o el 10 a cruzan su media de 200 sesiones **y** se mantienen 3 sesiones
   al otro lado (evita cruces de un día).
3. **Cambio de régimen**: cambia el cuadrante del clasificador en vivo, o una capa (crédito, liquidez, deuda) pasa a
   rojo/escasa.
4. **Dato macro sorpresa**: IPC/PCE subyacente, empleo (nóminas, paro) o PIB de EE. UU. publicados con una diferencia
   frente a la **previsión del propio proyecto** (nowcast/tendencia de 6 meses) ≥ **2 σ** de sus errores históricos.
   (No hay consenso de analistas gratis y fiable; se declara.)
5. **Flujos fuertes**: las alertas «fuertes» que ya existen (`src/report/alertas.py`: volumen anormal, Form 4, 13F,
   recompras) en un activo de «Mis activos», solo si coinciden con un movimiento de precio ≥ 2 σ.
- **Agrupación:** todos los disparadores del mismo día forman **un** evento (una nota), no uno por activo.
- **Enfriamiento:** el mismo disparador en el mismo activo no vuelve a generar nota en 5 sesiones (sí se añade como
  actualización a la nota abierta).

## 3. Contexto (paquete sin IA, reproducible)
- Movimientos del día en ~25 activos y sectores (en σ), y si la caída/subida es generalizada o concentrada.
- Correlaciones de 20 días frente a las de 1 año (¿cambió el régimen de correlaciones? p. ej. bolsa y bonos juntos).
- **Calendario**: qué datos macro se publicaron ese día y el anterior (fechas de publicación de ALFRED/FRED que ya
  tenemos), reuniones de bancos centrales.
- Posicionamiento: COT («Manos fuertes»), flujos de «Mis activos».
- Régimen y capas del día; qué decían ayer los modelos del proyecto (E1, INT-11) — sin re-correr nada.
- Episodios parecidos desde 2002 (mismo método que el informe del 18-nov).
- **Noticias (fuente nueva):** titulares del día de **GDELT** (gratis, sin clave) filtrados por los activos que se
  movieron, y comunicados oficiales (Fed, BLS, BEA, BCE) por RSS. Se guardan con su URL; la nota solo cita titulares
  que estén en el paquete.

## 4. La nota (formato fijo)
1. Aviso: «Explicación posterior; no es señal de compra o venta».
2. **Qué ha pasado** (solo datos del paquete, con cifras).
3. **Hipótesis de causa**, de más a menos probable (máximo 4), cada una con: evidencia a favor, evidencia en contra,
   confianza (alta/media/baja) y **qué dato de los próximos días la confirmaría o descartaría**.
4. Qué dicen los modelos del proyecto (sin re-correr) y si el movimiento estaba dentro de lo esperado.
5. Fuentes (URLs del paquete).
- **Seguimiento:** a los 5 y 20 días hábiles, una línea automática (sin IA) añade si los datos «que la confirmarían»
  llegaron. Con el tiempo, esto mide si las hipótesis de la nota aciertan (registro en `research/diag/aciertos.jsonl`).

## 5. Límites de coste y seguridad
- **Tope: 3 notas por semana** (si hay más eventos, se queda el de mayor tamaño; el resto solo como línea en «Hoy»).
- `claude -p` con herramientas **solo de lectura** del paquete y escritura en `obsidian/Diagnosticos/`; sin Bash, sin
  acceso a `alpaca.env` ni a `research/paper/`. Tiempo máximo por nota: 10 min.
- Las notas no se commitean solas (evita árbol sucio en los registros mensuales): las commitea la semanal.
- Si Claude falla o no hay red: la tarjeta en «Hoy» sale igual con el paquete de datos, sin hipótesis.

## 6. Plan de construcción
1. Disparadores + contexto (sin IA) con tests y **prueba en histórico**: ¿cuántos eventos habrían saltado en 2022-2026?
   (objetivo: 1-3 por semana de media; si salen muchos más, se sube el umbral **antes** de activar, y se anota).
2. Fuente GDELT/RSS con tests sin red.
3. Explicador `claude -p` + nota + tarjeta en «Hoy».
4. Ensayo: regenerar la nota del 18-nov automáticamente y compararla con el informe manual.
5. Validador → activar en la diaria.

## 7. Decisiones del usuario
- a) Umbrales de §2 (3 σ / 2,5 σ en ≥ 3 / media de 200 + 3 sesiones / 2 σ en datos macro).
- b) Tope de 3 notas por semana.
- c) Lista de activos de referencia de §2.1 (¿añadir alguno de «Mis activos»?).
- d) GDELT + RSS oficiales como fuente de noticias.
