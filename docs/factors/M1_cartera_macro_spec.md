---
documento: M1 «cartera macro» — prueba en vivo de los modelos macro del proyecto con una regla fija (Alpaca PAPER)
version: 0.1 BORRADOR (2026-11-19) — pendiente de aprobación del usuario; se congela ANTES del primer dato en vivo
estado: diseño; nada construido.
---

# M1: operar con lo que dicen los modelos macro

## 0. Qué es y qué no es
- Decisión del usuario (19-nov): «la intención es validar los modelos con carteras que se basen en la macro», con
  acciones y activos tipo futuros. M1 es la **traducción mecánica** de las salidas macro del proyecto a una cartera;
  compite con D1 (precio, sin macro), C1 (Claude, libre) y B0/B1/B1′.
- **Solo hacia delante.** Prueba fuera de muestra de verdad: la regla se congela antes del primer dato en vivo y no
  se toca (cambio = M1 v2, declarado).
- **Previo escéptico, declarado:** con historia ≤ 2004, convertir el régimen en pesos no mejoró (V1-V3 frente a B1;
  S1 frente al mercado, p = 0,50). M1 existe para comprobarlo en vivo con todos los modelos juntos, no porque se
  espere que gane.
- Sin futuros en Alpaca: ETFs que los siguen (DBC, USO, UUP, TLT…). Sin cortos ni apalancamiento.

## 1. Entradas (todas ya existen; última versión publicada al cierre de cada día)
| entrada | de dónde | frecuencia |
|---|---|---|
| cuadrante (G↑/↓, I↑/↓) | `signal.regime` (clasificador en vivo) | diaria/semanal |
| crédito (verde/ámbar/rojo) | `signal.credit.light` | diaria |
| liquidez (holgada/neutral/escasa) | `signal.liquidity.state` | diaria |
| P(recesión) E1 | último registro `research/int/e1_vivo.jsonl` | mensual |
| P(pérdida 12 m) de la bolsa EE. UU. | INT-11 `escenarios` | mensual |

## 2. Regla
**Paso 1 — cuánta bolsa** (base 60 %, suelo 20 %, techo 75 %):
- crédito ámbar −10 pp, rojo −25 pp;
- P(recesión) E1 > 30 % −15 pp, > 50 % −30 pp (no se suman: la mayor);
- liquidez escasa −5 pp, holgada +5 pp;
- INT-11 P(pérdida 12 m) bolsa > 60 % −10 pp, < 35 % +5 pp;
- cuadrante G↑ +10 pp, G↓ −10 pp.

**Paso 2 — qué bolsa** (dentro del % del paso 1):
- 50 % núcleo **VTI**;
- 30 % en los 4 sectores del cuadrante (mapa de S1, `config/alpaca_etfs_s1.json`), a partes iguales;
- 20 % en **acciones**: las 2 mayores por capitalización de cada sector favorecido (lista fija versionada
  `config/m1_acciones_v1.json`, revisada solo en enero), a partes iguales (8 acciones).

**Paso 3 — el resto** (100 % − bolsa), según la inflación:
- I↑: GLD 30 %, DBC 25 %, TIP 25 %, SHY 20 %;
- I↓: TLT 40 %, IEF 30 %, GLD 20 %, SHY 10 %;
- si crédito rojo **o** P(recesión) > 50 %: UUP 10 % de la cartera total, sacado de SHY/IEF.

**Cuándo opera:** cada día hábil tras el cierre (22:45 Madrid) recalcula; opera si cambia cualquier entrada que mueva
algún peso, o si un peso deriva ≥ 5 pp del objetivo. Órdenes limit ± 0,5 % para la sesión siguiente. Colchón 0,5 % en
efectivo.

## 3. Registro y evaluación
- Registro inmutable `research/paper/decisiones_m1.jsonl` (entradas usadas con su fecha de publicación, pesos,
  órdenes), commit y push diario; exige `research/paper/M1_ACTIVO`.
- Además del resultado, **atribución**: cuánto aporta cada entrada (rentabilidad de M1 frente a la misma cartera con
  esa entrada congelada en neutral), para saber qué modelo ayuda y cuál estorba.
- Listones: B0 (pasivo) y D1 (sin macro). Aviso en el panel: años para concluir.

## 4. Requisitos
Tercera cuenta paper del 2.º usuario de Alpaca, claves `_M1`.
