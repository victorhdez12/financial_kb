# Puerta de gasto (lectura, no criterio)

**Lectura:** se recomienda NO registrar todavía (decide el usuario). Mejora del pool frente a M0 (pool_dev, vintage) = +0.0395 nats, IC 95 % [-0.0080; +0.0862]. Potencia de la v4.3 si esta fuera la mejora verdadera ≈ 0.53.

| corrida | mejora | IC 95 % | IC 95 % (b24) | giros | estables | mismo signo |
|---|---|---|---|---|---|---|
| pool_dev | +0.0395 | [-0.0080; +0.0862] | [-0.0125; +0.0941] | +0.0275 | +0.0436 | True |
| pool_m1cmp | +0.0494 | [-0.0085; +0.1071] | [-0.0143; +0.1157] | +0.0333 | +0.0541 | True |
| pool_uno | +0.0393 | [-0.0079; +0.0856] | [-0.0119; +0.0930] | +0.0262 | +0.0438 | True |
| pool_excluir | +0.0133 | [-0.0262; +0.0525] | [-0.0271; +0.0546] | +0.0174 | +0.0119 | False |

| predicción | estado |
|---|---|
| P1 | m2_struct_g: no evaluable; m3_tvtp_g: no evaluable |
| P2 | no evaluable |
| P3 | no evaluable |
| P4 | pool_g: no evaluable; m2_struct_g: no evaluable; m3_tvtp_g: no evaluable |
| P5 | no se cumple del todo (no es falsa por su regla) |
| P6 | se cumple |
| P7 | pool_g: se cumple; m2_struct_g: se cumple |
| P8 | estado_media: se cumple; estado_sd: se cumple |
| P9 | no se cumple (sin regla 'falsa si') |
| P10 | fracciones γ > 0,01: gamma1 1.00, gamma2 0.91, gamma3 0.87, gamma4 1.00 |
| P11 | no se cumple del todo (no es falsa por su regla) |
