---
documento: protocolo PRERREGISTRADO del control sintético de M2 v1.3 con verdad construida con datos completos (control "completo")
fecha: 2026-10-25
autor: Validador independiente (redactado en sesión remota, solo lectura; commiteado por el Constructor)
objeto: m2_structural_spec.md v1.3 (d8eb113), implementación 90f408f, sin cambios de código de M2
base del repo: d9bfd8a (main). Antecedentes: control de 4 semillas (d892b93, NO superado, se declara); control ampliado de 2026-10-24 (da18753; resultado en docs/validation/2026-10-25_m2_v13_control_ampliado_resultado.md)
estado: escrito y commiteado ANTES de correr ninguna semilla nueva (2001-2040)
contacto_con_datos: NINGUNO. Solo datos sintéticos (tests/m2_synth.py). No se carga la etiqueta, ni la base PIT, ni niveles reales. No se registra nada en harness_runs ni en el trial log
script: tests/validation/m2_control_completo.py (se crea según §6; sha256 fijado en un commit anterior a cualquier corrida)
salida: research/validation/m2_control_completo/
---

# Control completo de M2 v1.3: protocolo prerregistrado

## 0. Qué se ha visto antes de escribir esto (declaración de no ciego)

- Control de 4 semillas (3, 7, 11, 21; `Synth(seed)`, fin 2004-12): coberturas del 80 % de 0,834 / 0,818 / 0,855 / 0,872. No superado; se declara y no se borra.
- Control ampliado (semillas 1001-1040):
  - Brazo A (fin 2004-12): c̄ = 0,8099; IC 95 % [0,7942; 0,8256]; 28/40 semillas en [0,75; 0,85]. Cumple principal y secundario (justo en 0,70).
  - Brazo B (fin 2009-12): c̄ = 0,8011; IC 95 % [0,7844; 0,8178]; 24/40 semillas en rango. Cumple principal; no cumple secundario (60 %).
  - R0 reproduce las coberturas de 3/7/11/21 con diferencia < 5e-11.
- Los estadísticos de calibración de A y B (z², cobertura 50 % y 95 %, subperiodos) están en `resumen.json` y no se usaron como criterio. Este protocolo fija que tampoco se usan para decidir.

**Consecuencia:** el control completo no es ciego. La expectativa a priori, con A y B, es c̄ ≈ 0,80-0,81 y sd entre semillas ≈ 0,05. Con esos valores:
- El criterio principal equivale aproximadamente a c̄ dentro de [0,766; 0,834] (semiamplitud del IC ≈ 0,016).
- La fracción esperada en rango es ≈ 0,68, justo por debajo de 0,70. El secundario es casi una moneda. Si el principal se cumple, lo más probable es el veredicto "cumple con reserva".

Se fija esto antes de correr para que no sorprenda.

## 1. Motivo y diseño

- En el control de 4 semillas y en el brazo A, la verdad G para T ≥ 2000-01 está truncada. La mediana centrada ±60 meses (`src/labels/regime_us.py`, `centered_median`, `trend_half_window = 60`) no tiene su ventana completa, porque la serie sintética termina en 2004-12.
- El control principal tiene que medir la cobertura frente a la misma verdad que usará la etiqueta real, con la ventana completa. Por eso el generador se extiende hasta 2009-12. Así, para todo T ≤ 2004-08, la ventana T ± 60 meses (≤ 2009-08) está completa.
- Alargar el generador no da información futura al modelo: `info(T)` solo entrega X ≤ T, y `pit_levels` aplica el retraso de publicación de cada serie. La trayectoria con fin 2009-12 no es la de fin 2004-12, porque las extracciones de ruido idiosincrático cambian.
- M2 no se modifica. `src/` no cambia.

## 2. Brazo principal, semillas y precondición

- **Brazo C (único brazo de criterio):** `Synth(seed, end="2009-12")`, semillas **2001, 2002, …, 2040** (40 semillas, todas, sin selección).
- **Por qué no 1001-1040:** ya se usaron en A y en B, y sus resultados son conocidos. Además, A y B con la misma semilla comparten la trayectoria del factor común f hasta 2004-12 (las primeras extracciones del RNG son idénticas; lo que cambia es el ruido idiosincrático u). Por tanto no son 40 realizaciones independientes respecto de A y B. Las semillas 2001-2040 no aparecen en ningún script, test, resultado ni documento del repo (búsqueda hecha el 2026-10-25 en tests/, src/, research/ y docs/).
- **R0 (precondición, no entra en el criterio):** semillas 3, 7, 11 y 21 con `Synth(seed)` (fin por defecto 2004-12) deben reproducir `research/trials/m2/controles_m2_v13.json` con diferencia < 1e-9. Si no, no se corre C.
- No se corre de nuevo el brazo B (1001-1040) ni el diagnóstico D3 del control anterior.

## 3. Cortes, bucle y verdad

- Cortes mensuales T = 1980-01 … 2004-08 (296 cortes), igual que en el control anterior (`src/models/pool_controls.py::m2_planted`, spec §6).
- En cada T: `m.fit_axis_continuous("G", …, s.info(T, data_key=…))`, luego `predict_axis_continuous`; μ y σ̂ de la predicción; z = (G − μ)/σ̂.
- Verdad: G = `s.true_G()` del generador con fin 2009-12. **Sin truncar** para ningún T.
- Aciertos: cobertura del 80 % si |z| < Φ⁻¹(0,9) = 1,2816; del 50 % si |z| < Φ⁻¹(0,75) = 0,6745; del 95 % si |z| < Φ⁻¹(0,975) = 1,96.
- **Integridad (obligatoria, antes de contar):** en cada semilla, los 296 cortes deben tener G, μ y σ̂ finitos, y σ̂ > 0. Si no, el control se para y se reporta. No se descarta la semilla ni se sustituye por otra. (El script anterior contaba un NaN como fallo de cobertura. Esta comprobación lo impide.)

## 4. Criterios (fijados)

Sea c̄ la media de las 40 coberturas del 80 %, sd su desviación típica entre semillas (ddof 1), y IC 95 % = c̄ ± t₀,₉₇₅;₃₉ · sd/√40, con t₀,₉₇₅;₃₉ = 2,0227.

- **Principal:** el IC 95 % completo queda dentro de [0,75; 0,85]. Se compara sin redondear; el informe se da con 4 decimales.
- **Secundario:** la fracción de semillas con cobertura del 80 % en [0,75; 0,85] es ≥ 0,70 (sin redondear). Informa; no decide por sí solo.

**Veredicto (fijado):**

| principal | secundario | veredicto | consecuencia |
|---|---|---|---|
| cumple | cumple | **CUMPLE** | M2 v1.3 queda habilitado para `m2_long`. Su lanzamiento sigue necesitando el visto bueno del usuario |
| cumple | no cumple | **CUMPLE CON RESERVA** (dispersión entre semillas) | igual que lo anterior, con la reserva escrita en el resultado |
| no cumple (por arriba o por abajo) | cualquiera | **NO CUMPLE** | no se corre `m2_long` con M2 v1.3 bajo este control. Se para y decide el usuario (§7). El secundario no rescata ni hunde el veredicto |

## 5. Diagnósticos (sin criterio; se informan, no deciden)

- Cobertura del 50 % y del 95 %: media y IC 95 % entre semillas.
- z² medio total y por subperiodos, 1980-01…1999-12 y 2000-01…2004-08, con IC 95 % entre semillas (ideal ≈ 1).
- Exceso de curtosis de z y sesgo medio de z (medias entre semillas).
- RMSE de G − μ, media de σ̂, número de versiones sin convergencia.
- Escala de la verdad: sd de G sobre los 296 cortes, por semilla, y su IC 95 %.
- **Error de Monte Carlo:** por semilla, SE de la cobertura del 80 % por bootstrap de bloques móviles (bloques de 12, 24 y 48 meses; 2.000 réplicas; semilla del bootstrap 12345), y n_efectivo = c(1 − c)/SE². Se compara con la sd entre semillas.
- Autocorrelación de los aciertos a 1, 3, 6, 12 y 24 meses.

Si algún diagnóstico llama la atención, se propone un protocolo nuevo. No se corrige este.

## 6. Script, fijación del hash y salida

**Script:** `tests/validation/m2_control_completo.py`. No existe en el repo a la fecha de este protocolo. Se crea copiando `tests/validation/m2_v13_control_ampliado.py` y cambiando SOLO lo siguiente (lista exhaustiva):

1. Brazo `C`: `Synth(seed, end="2009-12")`, con `data_key = f"validador_C_{seed}"`. Sustituye a A y B.
2. `SEEDS_NEW = tuple(range(2001, 2041))`. `run` acepta el brazo C solo con esas semillas, y R0 solo con 3, 7, 11, 21.
3. `OUT = REPO / "research" / "validation" / "m2_control_completo"`.
4. Comprobación de integridad de §3 (aserción de 296 cortes finitos y σ̂ > 0) antes de escribir el JSON de cada semilla.
5. `analyze()` solo con R0 y C. Calcula el principal y el secundario de §4, aplica el veredicto de §4 y los diagnósticos de §5. Se elimina la rama D3 y el flag `--d3`.

Nada más cambia. En particular no cambian: `vconj_errors`, el bucle de `run_seed`, `block_boot_se` (parámetros y semilla 12345), `Q80/Q50/Q95`, `LO/HI` ni `per_seed` (salvo la aserción). Cualquier otra diferencia con el script anterior invalida el control y exige un protocolo nuevo.

**Fijación del hash (orden obligatorio):**
1. Este protocolo se commitea y empuja. Es la referencia.
2. El Constructor crea el script y lo commitea solo, sin otros cambios. El mensaje del commit lleva el sha256 del fichero, y el mismo sha256 se escribe en `research/validation/m2_control_completo/script_sha256.txt` en ese commit. Después se empuja.
3. Solo entonces se corre nada.

**Verificación del Validador antes del veredicto:** (a) el sha256 del script en el commit de la fase 2 coincide con el del mensaje y con el del fichero; (b) el diff del script contra `m2_v13_control_ampliado.py` contiene solo los puntos 1-5; (c) `git diff <commit de este protocolo>..<commit del script> -- src/` está vacío; (d) no cambia ningún otro fichero salvo el script, `script_sha256.txt` y la salida.

**Ejecución:**
- `.venv/bin/python tests/validation/m2_control_completo.py run --arm R0 --seed {3,7,11,21}`
- `.venv/bin/python tests/validation/m2_control_completo.py run --arm C --seed {2001,…,2040}`
- `.venv/bin/python tests/validation/m2_control_completo.py analyze`

Las variables de hilos BLAS quedan a 1 (como en el script). Cada semilla es un proceso independiente, así que pueden correr en paralelo. **No se reduce el número de semillas por tiempo**, a diferencia del control anterior. Si es lento, se paraleliza. Si no basta, se para y decide el usuario.

**Salida:** `research/validation/m2_control_completo/` con `R0_<semilla>.json`, `C_<semilla>.json`, `resumen.json` y `script_sha256.txt`. No se escribe en `research/trials/`, ni en harness_runs, ni en el trial log. No se toca `research/validation/m2_v13_control_ampliado/`.

## 7. Qué pasa si el control falla

- **R0 no reproduce:** no se corre C. Se investiga el script (no M2) y se informa.
- **Integridad de §3 falla:** se para y se informa.
- **Veredicto NO CUMPLE:** no se itera el diseño. Queda prohibido, a la vista de C: añadir semillas; cambiar el generador, el fin de la serie, la ventana, los cortes, el criterio o los umbrales; elegir subconjuntos de semillas o de cortes; y cambiar M2. El Constructor entrega `resumen.json` y el resultado, y para. El usuario decide entre: (a) aceptar con reserva declarada; (b) un protocolo nuevo de diagnóstico (p. ej., H-b o H-c) con semillas nuevas; (c) un cambio de la spec por protocolo aparte.
- **Crash del script antes de escribir ningún `C_*.json`:** se corrige, se registra en un commit con su nuevo sha256 y se corre de nuevo. Si ya hay algún `C_*.json` escrito, no se corrige a mitad: se para y decide el usuario.
- **Resultado en rango pero diagnósticos malos** (z² lejos de 1, colas gruesas): no cambia el veredicto. Se informa.

## 8. Riesgos residuales que este protocolo reconoce

1. **Colas gruesas o heterocedasticidad (H-c):** una σ̂ con el ECM correcto puede sobre- o infracubrir el 80 % aunque E[z²] ≈ 1. La cobertura del 80 % es sensible a la forma de la distribución. Se mide con curtosis, z² y coberturas del 50 % y del 95 %, pero no se corrige aquí.
2. **Escala de σ de la verdad:** G se normaliza con σ = 1,4826 · MAD de las desviaciones de la muestra completa de cada semilla (`regime_us.robust_sd`, `growth_components`). Esa escala depende de la realización. σ̂ se estima con errores pseudo-tiempo-real. Si las escalas difieren de forma sistemática, la cobertura lo refleja, pero el control no lo separa de la forma de la distribución. Diagnóstico: sd de G por semilla.
3. **Mejor caso por construcción:** los datos son los del propio modelo de `m2_synth.py` (spec §3). Pasar el control no prueba calibración con datos reales. Solo prueba que la estimación y σ̂ son coherentes con el generador.
4. **No ciego (§0):** A y B se han visto. C es una réplica confirmatoria con verdad completa. Si C falla y B cumplía, la discrepancia es informativa, pero no se resuelve en este protocolo.
5. **Potencia y secundario:** con sd ≈ 0,05 la semiamplitud del IC es ≈ 0,016. El criterio principal es "la media cae dentro de una banda", no un contraste de igualdad. El secundario es casi una moneda (fracción esperada ≈ 0,68).
6. **Visión del futuro por el modelo:** que M2 solo use datos ≤ T se hereda del código sin cambios y no se vuelve a probar aquí. El control PIT de la spec §6 es el que lo cubre.
7. **Control de 4 semillas:** queda NO superado y declarado. Este protocolo no lo borra ni lo sustituye. Aquel control usaba verdad truncada.
8. **Uso de datos 2005-2009 en la verdad:** es intencionado (la verdad de T ≤ 2004-08 necesita la ventana completa). El modelo no ve esos datos al estimar.
