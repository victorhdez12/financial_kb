# Termómetro: puerta, 2.º y último intento (recalibración + validación cruzada)

Diseño v1.3 §9 (`a94ac09`); commit d21901f, árbol limpio True, 2026-10-29T12:35:54+00:00.

| giro | filas | r | pendiente | pasa | sin recalibrar r / pend |
|---|---|---|---|---|---|
| T1 | 190 | 0.788 | 0.794 | False | 0.793 / 0.680 |
| T2 | 31 | 0.818 | 0.906 | True | 0.890 / 0.869 |

Por país: T1 BEL 17 f, 0.828 / 0.968 True; T1 DEU 17 f, 0.875 / 0.928 True; T1 ESP 18 f, 0.894 / 0.908 True; T1 FIN 12 f, 0.688 / 0.495 False; T1 FRA 21 f, 0.782 / 0.791 False; T1 GBR 15 f, 0.671 / 0.598 False; T1 ITA 11 f, 0.850 / 0.973 True; T1 NLD 19 f, 0.803 / 0.815 True; T1 NOR 17 f, 0.885 / 1.019 True; T1 PRT 9 f, 0.683 / 0.732 False; T1 SWE 14 f, 0.720 / 0.786 False; T1 USA 20 f, 0.760 / 0.565 False

Veredicto: {'pasa_agregado': {'T1': False, 'T2': True}, 'paises_con_probabilidad': {'T1': [], 'T2': ['BEL', 'DEU', 'ESP', 'FIN', 'FRA', 'GBR', 'ITA', 'NLD', 'NOR', 'PRT', 'SWE', 'USA']}}

Percentiles de referencia (recalibrados, todos los años ≤ 2004): {'T1': {'meses': 2378, 'p50': 0.0775, 'p80': 0.1552, 'p95': 0.2986}, 'T2': {'meses': 295, 'p50': 0.816, 'p80': 0.9068, 'p95': 0.9552}}
