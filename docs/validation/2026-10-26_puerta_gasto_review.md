---
documento: revisión independiente de la puerta de gasto y la preparación del registro de P-EVAL-BASE
fecha: 2026-10-26
autor: Validador (rama claude/puerta-gasto-review)
objeto: origin/claude/puerta-gasto, commits f95c6aa (puerta de gasto) y be8bc74 (preparación del registro)
referencias: docs/models/pool_spec.md §5 y §5b; docs/models/p_eval_base_v4_draft.md v4.3 §A7, §A8, §A9; research/trials/harness_runs.jsonl (origin/main 8944baa, 20 entradas)
hashes: tests/validation/puerta_gasto.py sha256 772f1cbc9edd…; config/harness/p_eval_base.yaml sha256 3d0322627825…
restricciones: sin datos ni etiqueta reales; arnés no ejecutado (ni con --official ni sin él); nada registrado; nada fusionado; main sin tocar
---

# Revisión de la puerta de gasto (claude/puerta-gasto)

## Veredicto: ⚠️ usable tras corregir

- La preparación del registro (be8bc74) está bien. `config/harness/p_eval_base.yaml` es byte a byte el bloque de §A8 y no queda nada registrado ni activo.
- La puerta de gasto (f95c6aa) lee lo esencial de §5/§5b: IC pool − M0, subperiodos, giros/estables, pesos y (a, b), P1-P11.
- Pero sus controles de integridad dejan pasar corridas no oficiales (árbol sucio), repetidas y de otra versión de la configuración. El registro real ya contiene un caso así: `baselines_v1`, corrido dos veces y las dos con `git_dirty: true`.
- Además hay dos criterios añadidos (la regla de falsedad de P9 y el mecanismo a partir de P1 completo) y algunos elementos de §5 que no se leen.
- Ninguno de estos fallos altera los números que calcula. Todos afectan a qué corridas acepta o a cómo etiqueta el resultado.
- Las correcciones van como propuesta (diff al final), sin aplicar. Con ellas aplicadas el veredicto pasaría a ✅.

## Comprobaciones

### 1. Qué lee puerta_gasto.py frente a las specs

| Pide la spec | Lo lee | Nota |
|---|---|---|
| IC 95 % de la mejora pool − M0, bootstrap por bloques de 12 (A7, §5) | sí (`resumen_corrida`, l. 97-116; `puerta`, l. 263-271) | Recalcula el IC con `boot_mean` y lo compara con el registrado (l. 84) |
| Subperiodos y mismo signo (§5) | sí (l. 110-111) | Ver B3: en `pool_m1cmp` mezcla épocas |
| Giros / estables (§5) | sí (l. 106-109) | — |
| Trayectoria de pesos y (a, b) por corte (§5) | sí (`trayectoria_pesos`, l. 129-136) | — |
| sd mensual de d frente a componentes (§5b P8) | sí (`sd_frente_componentes`) | — |
| P1-P11 (§5b) | sí (l. 160-259) | Ver M1 y M2 |
| Detección de giros v2.1 frente a M0, 3 m × 80/20, calibración del eje G, prueba de signo por episodio (§5) | **no**: solo `falsas_alarmas_por_año` (l. 112-114) | M3 |
| La puerta es una lectura, no un criterio (A7) | sí: no bloquea nada, y el umbral de 0,05 queda como "efecto mínimo" | — |

### 2. Integridad frente a harness_runs.jsonl

Lo que comprueba hoy `cargar` (l. 66-86):
- que el run_id esté en el registro;
- que el nombre de la configuración sea el esperado;
- la log-loss media por modo/modelo (≤ 1e-9);
- el IC del principal recalculado (≤ 1e-12).

Lo que no comprueba (A1):
- `code.git_dirty` ni `phase`;
- que la configuración tenga una sola corrida registrada;
- que la configuración registrada sea la del YAML actual;
- que `report.json` coincida con la línea del registro.

Test nuevo, cinco casos: sucia, otra fase, repetida, otra config y report.json cambiado. Los cinco **pasan la puerta original sin error**, y los cinco se rechazan con la propuesta.

### 3. p_eval_base.yaml y estado del registro

- `config/harness/p_eval_base.yaml` es igual a `_a8_block()` del borrador de origin/main, comparado con `==` sobre el texto completo (test `test_config_is_exactly_the_a8_block`, en verde).
- `research/hypotheses.yaml` no contiene `P-EVAL-BASE`.
- La entrada preparada existe solo como bloque de texto en `docs/models/p_eval_base_registro.md`.
- No hay ninguna línea de P-EVAL-BASE en `research/holdout/dry_runs.jsonl`.
- **Nada registrado ni activo.**

El checklist (A9) es coherente con la cadena real: el hash del ensayo en seco cubre config + `src/models` + dependencias PIT (`prereg_config_sha`), y `_preflight` exige la línea `ok` con ese mismo sha.

### 4. Tests

- `tests/test_p_eval_base_registro.py`: 3 tests, cubren lo necesario.
- `tests/test_puerta_gasto.py`: 3 tests (lectura completa; P1/P2 no evaluables sin las corridas largas; parada ante id no registrado, ante una corrida de otra configuración y ante scores.parquet alterado). **No cubren** los casos de A1 ni M1/M2.
- Además, el test de alteración modifica los artefactos del fixture de módulo, que comparten todos los tests (B6).

## Hallazgos

### ALTO

**A1. La integridad no rechaza corridas no oficiales, repetidas ni de otra versión** (`tests/validation/puerta_gasto.py:66-86`).
- Una corrida con `git_dirty: true`, o con fase distinta de `development`, se acepta.
- Un segundo run de la misma configuración se acepta. Con eso, quien lanza la puerta puede elegir el más favorable, en contra de "una sola pasada" (A7).
- Una corrida hecha con otra versión del YAML (por ejemplo, con `philly_pre1990_nan` cambiado) se acepta, porque solo se compara el nombre.
- `report.json` no se ata a la línea del registro. Se puede cambiar el IC de `report.json` sin que la comprobación lo vea, salvo el recálculo de `boot_mean`, que solo cubre el principal y el modo `vintage`.

Evidencia real: en `research/trials/harness_runs.jsonl` de origin/main (20 entradas), `baselines_v1` aparece dos veces (20261016-091604 y 20261016-092402), ambas con `git_dirty: true`. El caso no es teórico.

Propuesta: exigir fase `development` (en la línea y en su config), `git_dirty` falso, una sola corrida por nombre, la config registrada igual a `asdict(HarnessConfig.from_yaml(...))` en las claves que definen la corrida, y media/lo/hi del principal de `report.json` iguales a los del registro.

### MEDIO

**M1. La prueba del mecanismo usa P1 completo (entrada y salida); la spec habla solo de la entrada** (l. 255-259).
- §5b: "si ni 1980 ni 2001 muestran ganancia en la entrada, el mecanismo falla".
- El código marca `mecanismo_falla` cuando P1 y P4 son "es falsa". Pero P1 es falsa también si la salida es ≤ 0 con entrada positiva (l. 174 y 181: `en <= 0 or sa <= 0`).
- Resultado: puede declarar que falla el mecanismo con ganancias en la entrada. Es un criterio añadido.
- Propuesta: `sin_ganancia_entrada_1980` / `_2001` (todas las entradas ≤ 0), y `mecanismo_falla` = las dos.

**M2. P9 tiene una regla de falsedad que la spec no da** (l. 238).
- §5b enuncia P9 como expectativa ("M3 − CTP ≤ +0,02"), sin cláusula "falsa si".
- El código la marca "es falsa" cuando dif > 0,02, lo que la pone al nivel de P1/P4.
- Propuesta: "se cumple" / "no se cumple (sin regla 'falsa si')".

**M3. Elementos de §5 sin leer**: detección v2.1 frente a M0, 3 m × 80/20, calibración del eje G y prueba de signo por episodio.
- Están en `report.json` (`deteccion_giros_g`, `por_episodio`, `calibracion`), pero la puerta solo copia las falsas alarmas.
- La puerta no decide nada con ellos. Aun así, §5 los lista como lectura obligada antes de gastar.
- Propuesta: copiarlos tal cual en `resumen_corrida` (sin umbrales nuevos).

**M4. No se comprueba que las corridas del pool sean de la misma versión del código.**
- `pool_dev`, `pool_m1cmp`, `pool_uno` y `pool_excluir` se comparan entre sí (P8, P11, pesos). Si el `src_models` difiere, la comparación mezcla versiones.
- Propuesta: aviso (no parada) en `lectura["avisos"]`. Solo un aviso, porque M2/M3 largos pueden ser legítimamente anteriores.

**M5. Los tests no cubren los fallos de A1, M1 y M2.** Propuesta: 6 casos nuevos (en el diff). Contra el código original: 6 fallan y 3 pasan; con la propuesta: 9 pasan.

### BAJO

- **B1.** "Claramente" (§5b) se operacionaliza como `lo ≤ 0` (l. 267) sin declararlo, y la ventana de P6 (1987-09 a 1988-03, ±3 m para el giro, l. 206-210) tampoco se declara. Son razonables, pero tienen que quedar escritas en la salida. Propuesta: bloque `operacionalizacion` en `lectura`.
- **B2.** Las ventanas de `EPISODIOS` (l. 44-48) son una lectura del Validador sobre la cronología NBER. Están en el docstring, pero no en la salida (se incluyen en el mismo bloque de B1).
- **B3.** En `pool_m1cmp`, `por_periodo` del arnés mezcla épocas (la ventana es más larga que 1985-2004), así que los "subperiodos" no son los de §5. Se informa tal cual. Hay que leerlo sabiéndolo.
- **B4.** La potencia del `POT_V43` (l. 49) se interpola linealmente entre puntos de la tabla de potencia: es orientativa, no una estimación. El texto de la salida debería decirlo.
- **B5.** La ruta por defecto de `harness_runs.jsonl` (`main`, `trials.V.trials_dir()`) sigue `FKB_TRIALS_DIR`. Si esa variable apunta a un directorio de pruebas, la puerta lee un registro de pruebas sin avisar. Recomendación: pasar `--harness-runs` explícito en el checklist.
- **B6.** El test de alteración modificaba `scores.parquet` del fixture compartido, de modo que el orden de los tests importa. Corregido en la propuesta (copia a `tmp_path`). También salen 20 `RuntimeWarning` en los tests (salen de `harness.score`, `src/models/harness.py:844`, con las series sintéticas del test, no de la puerta): no afectan a las aserciones, pero conviene filtrarlas en el test.

## Lo que no se puede verificar sin datos

- Que las corridas reales de `pool_*` y `m3_long` existan y pasen la integridad.
- Que `report.json` real tenga todas las claves que se leen. Sí se probó con artefactos sintéticos generados por `harness.score` + `trials.record`, es decir, con el formato real.
- Los valores de P1-P11 y la lectura de la puerta.

## Ejecución

Venv limpio, `PYTHONPATH=. FIN_DATA_ROOT=<vacío>`, registros en directorio temporal, sin datos:

| Código | tests/test_puerta_gasto.py | tests/test_p_eval_base_registro.py |
|---|---|---|
| Original (be8bc74) + tests nuevos | 6 fallan, 3 pasan | 3 pasan |
| Propuesta + tests nuevos | 9 pasan | 3 pasan |

## Propuesta de corrección (NO aplicada)

`git apply` sobre be8bc74. Toca `tests/validation/puerta_gasto.py` (+43/−6) y `tests/test_puerta_gasto.py` (+52/−1).

```diff
diff --git a/tests/test_puerta_gasto.py b/tests/test_puerta_gasto.py
index aa74575..78184a5 100644
--- a/tests/test_puerta_gasto.py
+++ b/tests/test_puerta_gasto.py
@@ -97,6 +97,9 @@ def artefactos(tmp_path_factory):
     mp.setenv("FKB_RUNS_DIR", str(d / "runs"))
     mp.setenv("FKB_TRIALS_DIR", str(d / "trials"))
     mp.setenv("FKB_TRIAL_LOG", str(d / "trial_log.md"))
+    from src.models import trials
+    mp.setattr(trials, "code_sha", lambda: {"src_models": "s" * 64, "pit_labels_deps": "p" * 64,
+                                            "git_head": "h" * 40, "git_dirty": False})   # corrida "oficial"
     ids = {k: _registrar(PG.NAMES[k], mp, d, seed=i) for i, k in enumerate(PG.NAMES)}
     yield ids, d
     mp.undo()
@@ -131,8 +134,56 @@ def test_puerta_without_m2_m3_long_marks_1980_as_not_evaluable(artefactos):
     assert res["predicciones_estratega"]["P2"]["estado"] == "no evaluable"
 
 
-def test_puerta_stops_on_tampered_or_unregistered_artifacts(artefactos, tmp_path):
+def _copia(d, tmp_path):
+    import shutil
+    shutil.copytree(d, tmp_path / "c")
+    return tmp_path / "c"
+
+
+def _reescribe_registro(hr, run_id, cambio):
+    rows = [json.loads(x) for x in hr.read_text().splitlines() if x.strip()]
+    for r in rows:
+        if r["run_id"] == run_id:
+            cambio(r)
+    hr.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))
+
+
+@pytest.mark.parametrize("caso", ["sucia", "desarrollo_no", "repetida", "otra_config", "report_cambiado"])
+def test_puerta_rejects_unofficial_repeated_or_other_version_runs(artefactos, tmp_path, caso):
+    ids, d0 = artefactos
+    d = _copia(d0, tmp_path)
+    hr = d / "trials" / "harness_runs.jsonl"
+    rid = ids["pool_dev"]
+    if caso == "sucia":
+        _reescribe_registro(hr, rid, lambda r: r["code"].update(git_dirty=True))
+    elif caso == "desarrollo_no":
+        _reescribe_registro(hr, rid, lambda r: r.update(phase="holdout_evaluation"))
+    elif caso == "repetida":
+        rows = [json.loads(x) for x in hr.read_text().splitlines() if x.strip()]
+        dup = {**[r for r in rows if r["run_id"] == rid][0], "run_id": rid + "_bis"}
+        hr.write_text(hr.read_text() + json.dumps(dup, ensure_ascii=False, default=str) + "\n")
+    elif caso == "otra_config":
+        _reescribe_registro(hr, rid, lambda r: r["config"]["model_params"]["m2_struct_g"].update(philly_pre1990_nan=True))
+    else:
+        rp = d / "runs" / rid / "report.json"
+        j = json.loads(rp.read_text())
+        j["report"]["frente_al_baseline"]["vintage/pool_g"]["mejora_logloss"]["hi"] += 0.01
+        rp.write_text(json.dumps(j))
+    with pytest.raises(PG.Integridad):
+        PG.lectura(ids, d / "runs", hr)
+
+
+def test_mechanism_uses_entries_only_and_p9_has_no_falsity_rule(artefactos):
     ids, d = artefactos
+    p = PG.lectura(ids, d / "runs", d / "trials" / "harness_runs.jsonl")["predicciones_estratega"]
+    assert set(p["prueba_del_mecanismo"]) == {"sin_ganancia_entrada_1980", "sin_ganancia_entrada_2001",
+                                              "mecanismo_falla"}
+    assert p["P9"]["estado"] != "es falsa"
+
+
+def test_puerta_stops_on_tampered_or_unregistered_artifacts(artefactos, tmp_path):
+    ids, d0 = artefactos
+    d = _copia(d0, tmp_path)                 # no modificar los artefactos compartidos del módulo
     hr = d / "trials" / "harness_runs.jsonl"
     with pytest.raises(PG.Integridad):
         PG.lectura({**ids, "pool_dev": "20990101-000000_pool_dev_deadbeef"}, d / "runs", hr)
diff --git a/tests/validation/puerta_gasto.py b/tests/validation/puerta_gasto.py
index 61b2428..c67e98d 100644
--- a/tests/validation/puerta_gasto.py
+++ b/tests/validation/puerta_gasto.py
@@ -45,6 +45,11 @@ EPISODIOS = {"1980": {"A→B": ("1979-06", "1980-06"), "B→A": ("1980-03", "198
              "1981-82": {"A→B": ("1981-01", "1982-03"), "B→A": ("1982-06", "1983-06")},
              "1990-91": {"A→B": ("1989-06", "1991-03"), "B→A": ("1991-01", "1992-06")},
              "2001": {"A→B": ("2000-06", "2001-12"), "B→A": ("2001-09", "2003-06")}}
+# claves de la configuración que tienen que coincidir con el YAML commiteado (lo que cambia la corrida)
+CLAVES_CONFIG = ("models", "model_params", "modes", "matrix_variant", "refit_every", "embargo_months",
+                 "min_train_months", "min_train_recessions", "min_train_g_changes", "test_start", "test_end",
+                 "eval_window", "allow_shrink", "feature_policy", "pit_version", "provisional_weighting", "baseline",
+                 "phase")
 # potencia de P-EVAL-BASE v4.3 (A7, estructural): Δ verdadera → potencia
 POT_V43 = ([0.0, 0.03, 0.05, 0.07, 0.10], [0.024, 0.41, 0.66, 0.80, 0.89])
 
@@ -63,12 +68,29 @@ def _registro(harness_runs: Path) -> dict:
     return out
 
 
+def _norm(x):
+    return json.loads(json.dumps(x, default=str))
+
+
 def cargar(run_id: str, clave: str, runs_dir: Path, reg: dict) -> dict:
+    from dataclasses import asdict
+    from src.models import harness as H
     if run_id not in reg:
         raise Integridad(f"{run_id} no está en harness_runs.jsonl")
     e = reg[run_id]
     if e["config"]["name"] != NAMES[clave]:
         raise Integridad(f"{run_id}: configuración {e['config']['name']!r}, se esperaba {NAMES[clave]!r}")
+    if e.get("phase") != "development" or e["config"].get("phase") != "development":
+        raise Integridad(f"{run_id}: fase {e.get('phase')!r} (solo corridas de desarrollo)")
+    if e.get("code", {}).get("git_dirty") is not False:
+        raise Integridad(f"{run_id}: git_dirty = {e.get('code', {}).get('git_dirty')!r} (no es una corrida oficial)")
+    otras = sorted(k for k, v in reg.items() if v["config"]["name"] == NAMES[clave] and k != run_id)
+    if otras:
+        raise Integridad(f"{run_id}: hay más corridas registradas de {NAMES[clave]} ({otras}): una sola pasada")
+    yml = asdict(H.HarnessConfig.from_yaml(H.REPO / "config" / "harness" / f"{NAMES[clave]}.yaml"))
+    dif = [k for k in CLAVES_CONFIG if _norm(e["config"].get(k)) != _norm(yml.get(k))]
+    if dif:
+        raise Integridad(f"{run_id}: la configuración registrada no es la commiteada en {NAMES[clave]}.yaml: {dif}")
     d = runs_dir / run_id
     rj = json.loads((d / "report.json").read_text())
     S = pd.read_parquet(d / "scores.parquet")
@@ -83,6 +105,9 @@ def cargar(run_id: str, clave: str, runs_dir: Path, reg: dict) -> dict:
     b = M.boot_mean(serie_d(S, p).to_numpy())
     if max(abs(b["lo"] - reg_ci["lo"]), abs(b["hi"] - reg_ci["hi"]), abs(b["mean"] - reg_ci["mean"])) > 1e-12:
         raise Integridad(f"{run_id}: boot_mean(d de {p}) no reproduce el IC registrado")
+    rj_ci = rj["report"]["frente_al_baseline"][f"{MODE}/{p}"]["mejora_logloss"]
+    if any(rj_ci[k] != reg_ci[k] for k in ("mean", "lo", "hi")):
+        raise Integridad(f"{run_id}: report.json no corresponde a la corrida registrada (IC de {p} distinto)")
     return {"run_id": run_id, "rep": rj["report"], "diag": rj.get("diag", {}), "S": S, "entrada": e}
 
 
@@ -112,6 +137,10 @@ def resumen_corrida(r: dict, model: str = POOL) -> dict:
     det = r["rep"].get("deteccion_giros_g", {}).get(f"{MODE}/{model}")
     if det:
         out["falsas_alarmas_por_año"] = det["falsas_alarmas_por_año"]
+    out["deteccion_v21_frente_a_M0"] = c.get("deteccion_frente_al_comparador")          # pool_spec §5 (detección v2.1)
+    out["episodios_prueba_signo"] = c.get("por_episodio", {}).get("resumen")             # episodios
+    out["deteccion_8020"] = r["rep"].get("deteccion_declarada_8020", {}).get(f"{MODE}/{model}")   # 3 m × 80/20
+    out["calibracion_G"] = r["rep"].get("calibracion", {}).get(f"{MODE}/{model}", {}).get("G")    # calibración
     return out
 
 
@@ -235,7 +264,7 @@ def predicciones(runs: dict) -> dict:
     if f"{MODE}/{M3}" in fb and f"{MODE}/{CTP}" in fb:
         dif = fb[f"{MODE}/{M3}"]["mejora_logloss"]["mean"] - fb[f"{MODE}/{CTP}"]["mejora_logloss"]["mean"]
         out["P9"] = {"m3_menos_ctp": dif, "corrida": NAMES["m3_long" if m3l else "pool_dev"],
-                     "estado": _estado(dif <= 0.02, dif > 0.02)}
+                     "estado": "se cumple" if dif <= 0.02 else "no se cumple (sin regla 'falsa si')"}
     else:
         out["P9"] = {"estado": "no evaluable"}
     # P10: fracción de cortes con γ > 0,01 (γ1 ≥ 50 % con alta probabilidad; γ3 < 50 % con prob. ≈ 0,5)
@@ -253,10 +282,12 @@ def predicciones(runs: dict) -> dict:
                   {"corte": last["corte"], "w_m0": last["w_m0"], "a": last["a"], "b": last["b"],
                    "estado": _estado(0.35 <= last["w_m0"] <= 0.7 and last["a"] >= 1 and last["b"] >= 1, None)})
     # prueba del mecanismo: si ni 1980 ni 2001 muestran ganancia en la entrada (P1 y P4 falsas), no tiene sentido gastar
-    f1 = any(v["estado"] == "es falsa" for v in p1.values())
-    f4 = any(v["estado"] == "es falsa" for v in p4.values())
-    out["prueba_del_mecanismo"] = {"P1_falsa": f1, "P4_falsa": f4,
-                                   "mecanismo_falla": bool(f1 and f4) if p1[M2]["estado"] != "no evaluable" else None}
+    en80 = [v["entrada"] for v in p1.values() if v["entrada"] is not None]        # SOLO la entrada (pool_spec §5b)
+    en01 = [v["entrada"] for v in p4.values() if v["entrada"] is not None]
+    sin80, sin01 = (bool(en80) and all(x <= 0 for x in en80)), (bool(en01) and all(x <= 0 for x in en01))
+    out["prueba_del_mecanismo"] = {"sin_ganancia_entrada_1980": sin80 if en80 else None,
+                                   "sin_ganancia_entrada_2001": sin01 if en01 else None,
+                                   "mecanismo_falla": (sin80 and sin01) if en80 and en01 else None}
     return out
 
 
@@ -274,13 +305,19 @@ def puerta(rs: dict) -> dict:
 def lectura(ids: dict, runs_dir: Path, harness_runs: Path) -> dict:
     reg = _registro(harness_runs)
     runs = {k: cargar(v, k, runs_dir, reg) for k, v in ids.items() if v}
+    codigos = {runs[k]["entrada"]["code"]["src_models"] for k in runs if k.startswith("pool")}
     res = {"run_ids": {k: v["run_id"] for k, v in runs.items()},
            "pool_frente_a_M0": {k: resumen_corrida(runs[k]) for k in ("pool_dev", "pool_m1cmp", "pool_uno",
                                                                         "pool_excluir")},
            "sd_mensual_d": {k: sd_frente_componentes(runs[k]) for k in ("pool_dev", "pool_m1cmp")},
            "componentes_frente_a_M0_pool_dev": {m: resumen_corrida(runs["pool_dev"], m) for m in (M2, M3, CTP)},
            "trayectoria_pesos": {k: trayectoria_pesos(runs[k]) for k in ("pool_dev", "pool_uno", "pool_excluir")},
-           "predicciones_estratega": predicciones(runs)}
+           "predicciones_estratega": predicciones(runs),
+           "avisos": (["las corridas del pool usan versiones distintas de src/models: "
+                       + ", ".join(sorted(c[:12] for c in codigos))] if len(codigos) > 1 else []),
+           "operacionalizacion": {"ic_incluye_0": "límite inferior del IC 95 % ≤ 0 (la spec dice 'incluye claramente')",
+                                  "episodios": EPISODIOS, "P6": "pg de M3 < 0,5 en 1987-09 … 1988-03 sin giro A→B en "
+                                  "1987-06 … 1988-06"}}
     res["puerta_de_gasto"] = puerta(res["pool_frente_a_M0"]["pool_dev"])
     return res
 
```
