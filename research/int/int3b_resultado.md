# INT-3b / INT-3c: resultado de la corrida única

Procedencia: commit `3281129`, árbol limpio True, 2026-10-26T19:13:17+00:00. Prerregistro v1.0 (fa6d4c9). Unidades: pp por año; en B1, B2 y C5, efecto de pasar del 0 % al 100 % de países del núcleo en el estado (entre paréntesis, por 1 dt de la cuota y la lectura por mayoría).

| id | pregunta | efecto (pp) | IC 95 % | p (NW/DK) | φ | p_cal | Holm | > p95 placebo | 1950-99 | países | ESTABLECIDO |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | mp_real × infl_alta | +0.7 (+0.2 por dt; mayoría -2.5) | [-13.6; +15.0] | 0.9236 | 1.10 | 0.9304 | no | no | -10.9 | 1878-1949: +11.6 | **no** |
| B2 | mp_real × recesion | -17.4 (-3.7 por dt; mayoría -7.7) | [-37.1; +2.2] | 0.0814 | 1.12 | 0.1178 | no | no | -28.8 | 1878-1949: -20.4 | **no** |
| B3 | oro_log × infl_alta | -6.0 | [-9.5; -2.6] | 0.0007 | 1.03 | 0.0010 | sí | sí | -4.7 | 1/14 sin encoger; 0/14 DL sin año | **no** |
| B4 | exceso_credito × recesion | -0.7 | [-1.9; +0.5] | 0.2235 | 1.14 | 0.2863 | no | no | -1.0 | 2/2 sin encoger; 0/2 DL sin año | **no** |
| C1 | eq_valoracion × estanflacion | +1.6 | [-2.9; +6.1] | 0.4751 | 1.14 | 0.5318 | no | no | +0.5 | 6/14 sin encoger; 4/14 DL sin año | **no** |
| C3 | bono_capital × infl_alta | -1.7 | [-3.1; -0.3] | 0.0147 | 1.15 | 0.0338 | no | sí | -1.4 | 13/14 sin encoger; 14/14 DL sin año | **no** |
| C4 | bono_capital × crec_bajo | +2.5 | [+1.6; +3.5] | 0.0000 | 1.00 | 0.0000 | sí | sí | +3.4 | 14/14 sin encoger; 14/14 DL sin año | **sí** |
| C5 | mp_spot_exceso_suma × infl_alta | +1.9 (+0.5 por dt; mayoría -2.2) | [-12.2; +16.1] | 0.7890 | 1.12 | 0.8114 | no | no | -11.0 | 1878-1949: +15.5 | **no** |

Criterios por pregunta: ver `criterios` en el JSON. Descriptivas y sensibilidades: en el JSON (no deciden).
