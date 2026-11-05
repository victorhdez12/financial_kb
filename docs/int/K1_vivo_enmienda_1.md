# P-K1v — enmienda 1 (2026-11-05, tras el Validador local; antes de registrar nada)
1. **Desfase del registro (igual que en desarrollo):** el 4.º trimestre de t se publica hacia junio-julio de t + 1, así
   que cada predicción para t + 1 se registra con media ventana ya pasada. En INT-6 pasaba lo mismo (x_t "conocido el
   30 de abril de t + 1" para un inicio en t + 1). Se mantiene para no cambiar el modelo.
   - **Inicios de crisis en t + 1 anteriores a la fecha de registro:** se registran igual, con la marca
     `inicio_previo_al_registro = true`, y quedan **fuera del contraste principal** (sensibilidad: dentro).
2. **Revisión anual de inicios:** antes de cada junio se declaran los inicios de crisis del año anterior en
   `scripts/k1_vivo.py` (`INICIOS_DESDE_2021`) y se sube `INICIOS_REVISADOS_HASTA`; sin eso el registro se niega
   (código 6). Fuente y prioridad: §4 del prerregistro.
3. **País que deja de publicar:** si en el año t un país no tiene el 4.º trimestre a 31 de diciembre de t + 1, se
   registra el resto y ese país como "sin dato" (para que un país no bloquee el registro para siempre).
4. **Contaminación ampliada (declarada):** leer `crisisjst` 2005-2020 gasta la cronología de crisis del bloqueado para
   cualquier pregunta con crisis bancarias (K1 y también G1 de INT-6), no solo para K1.
5. Puente JST→BIS: `scripts/k1_puente.py` (solo ≤ 2004, sin crisis).
