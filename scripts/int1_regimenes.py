"""INT-1: régimen ex post por país y fechado de recesiones (≤ 2004). Sin rentabilidades de activos, sin etiqueta de EE. UU.
Parámetros en src/intl/regimes.py. Reglas fijadas ANTES de correr (commit previo a la ejecución):
- Anual (JST, 1870-2004): G = crecimiento del PIB real per cápita (rgdpmad) frente a su media centrada de 11 años;
  I = inflación del IPC; principal relativa + 2 %, sensibilidad absoluta 3 %. Recesiones JST (normales / financieras).
- Mensual (OCDE, 1955-2004): G = log de la producción industrial frente a su tendencia centrada de 121 meses (brecha
  suavizada 7 meses). El paro NO entra en la etiqueta principal (interpolado o ausente en 10 de 18 países). I = IPC
  interanual. Recesiones: Bry-Boschan sobre log IP.
- Puerta (declarada antes de correr): picos de Bry-Boschan de EE. UU. frente a los picos del NBER (USREC) 1955-2004 con
  tolerancia ± 6 meses: ≥ 80 % detectados. Informativo: los 6 países euro del núcleo (BEL, DEU, ESP, FRA, ITA, NLD)
  frente a los picos CEPR de la zona euro (1974-07, 1980-01, 1992-01; trimestres → mes central), tolerancia ± 9 meses;
  y picos anuales JST de EE. UU. frente a los años de pico del NBER.
- Países de prueba (AUS, CHE, CAN, IRL): se calculan y se publican aparte; no entran en ninguna elección.
Uso: .venv/bin/python -m scripts.int1_regimenes
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import panel as P
from src.intl import regimes as G
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
DEST = db.DATA_ROOT / "intl"
PRUEBA = {"AUS", "CHE", "CAN", "IRL"}
NUCLEO = [c for c in D.PAISES if c not in PRUEBA]
EURO = ["BEL", "DEU", "ESP", "FRA", "ITA", "NLD"]
CEPR_PICOS = [pd.Timestamp(x) for x in ("1974-08-01", "1980-02-01", "1992-02-01")]


def rachas(s: pd.Series) -> pd.DataFrame:
    s = s.dropna()
    g = (s != s.shift()).cumsum()
    return s.groupby(g).agg(["first", "size"])


def main() -> None:
    con = D.connect()
    anual_p = P.anual(con)
    usrec = P._mensual_completa(D.load_dev(con, "USREC"))
    ip, cpi = {}, {}
    for c in D.PAISES:
        ip[c] = P._mensual_completa(D.load_dev(con, f"oecd_ip_{c.lower()}"))
        cpi[c] = P._mensual_completa(D.load_dev(con, f"oecd_cpi_{c.lower()}_idx"))
    con.close()

    res = {"paises": {}, "nucleo": NUCLEO, "prueba": sorted(PRUEBA)}
    et_a, et_m, rec_a, rec_m = [], [], [], []
    for c in D.PAISES:
        r = {}
        # anual
        if c in anual_p.index.get_level_values(0):
            a = anual_p.loc[c]
            crec, infl = a["pib_real_g"], a["inflacion"]
            for nom, kw in (("principal", {}), ("abs3", {"umbral_i": G.UMBRAL_I_ABSOLUTO, "relativa": False})):
                e = G.etiqueta(crec, infl, G.VENTANA_ANUAL, **kw)
                ok = e["cuadrante"].notna()
                r[f"anual_{nom}"] = {"años": int(ok.sum()), "desde": int(e.index[ok].min()) if ok.any() else None,
                                     "pct": e.loc[ok, "cuadrante"].value_counts(normalize=True).round(3).to_dict(),
                                     "frontera_pct": round(float(e.loc[ok, "frontera"].mean()), 3),
                                     "rachas_media": round(float(rachas(e.loc[ok, "cuadrante"])["size"].mean()), 2)}
                if nom == "principal":
                    et_a.append(e.assign(pais=c).reset_index(names="año"))
            ra = G.recesiones_anuales(a["rgdpmad"], a["crisisjst"])
            r["recesiones_anuales"] = {"total": len(ra), "financieras": int((ra.tipo == "financiera").sum()),
                                       "desde_1950": int((ra.pico >= 1950).sum())}
            rec_a.append(ra.assign(pais=c))
        # mensual
        x = np.log(ip[c]) if len(ip[c]) else pd.Series(dtype=float)
        ii = np.log(cpi[c]).diff(12) if len(cpi[c]) else pd.Series(dtype=float)
        if len(x.dropna()) > 240 and len(ii.dropna()) > 240:
            idx = x.index.union(ii.index)
            e = G.etiqueta(x.reindex(idx), ii.reindex(idx), G.VENTANA_MENSUAL, suavizado=G.SUAVIZADO_MENSUAL)
            ok = e["cuadrante"].notna()
            r["mensual"] = {"meses": int(ok.sum()), "desde": str(e.index[ok].min().date()),
                            "pct": e.loc[ok, "cuadrante"].value_counts(normalize=True).round(3).to_dict(),
                            "frontera_pct": round(float(e.loc[ok, "frontera"].mean()), 3),
                            "rachas_media_meses": round(float(rachas(e.loc[ok, "cuadrante"])["size"].mean()), 1)}
            et_m.append(e.assign(pais=c).reset_index(names="fecha"))
            bb = G.bry_boschan(x[x.index >= "1955-01-01"])
            r["bry_boschan"] = {"picos": int((bb.tipo == "pico").sum()), "valles": int((bb.tipo == "valle").sum())}
            rec_m.append(bb.assign(pais=c))
            if c in EURO:
                r["vs_cepr"] = G.concordancia(list(bb[bb.tipo == "pico"].fecha), CEPR_PICOS, 9)
        res["paises"][c] = r
    # puerta: EE. UU. frente al NBER
    u = usrec[usrec.index >= "1955-01-01"]
    nber = [u.index[i - 1] for i in range(1, len(u)) if u.iloc[i] == 1 and u.iloc[i - 1] == 0]
    bbu = rec_m[D.PAISES.index("USA")] if False else pd.concat(rec_m).query("pais == 'USA'")
    puerta = G.concordancia(list(bbu[bbu.tipo == "pico"].fecha), nber, 6)
    puerta["falsos_picos"] = int((bbu.tipo == "pico").sum()) - puerta["detectados"]
    res["puerta_usa_nber"] = {**puerta, "cumple_80": bool(puerta["pct"] is not None and puerta["pct"] >= 0.80)}
    ea = [res["paises"][c]["vs_cepr"]["pct"] for c in EURO if "vs_cepr" in res["paises"][c]]
    res["euro_vs_cepr_media"] = round(float(np.mean(ea)), 3) if ea else None
    ra_us = pd.concat(rec_a).query("pais == 'USA'")
    nber_años = sorted({d.year for d in nber})
    res["usa_anual_vs_nber_años"] = {"nber": nber_años, "jst_picos_desde_1955": sorted(ra_us[ra_us.pico >= 1955].pico.tolist())}
    # recuento de episodios (para INT-2): rachas por cuadrante (núcleo, anual principal) y recesiones
    A = pd.concat(et_a)
    epi = {}
    for c in NUCLEO:
        s = A[A.pais == c].set_index("año")["cuadrante"].dropna()
        for k, n in rachas(s)["first"].value_counts().items():
            epi[k] = epi.get(k, 0) + int(n)
    R_a = pd.concat(rec_a)
    res["episodios_nucleo_anual"] = {"rachas_por_cuadrante": epi,
                                     "recesiones": int(R_a[R_a.pais.isin(NUCLEO)].shape[0]),
                                     "recesiones_financieras": int(R_a[R_a.pais.isin(NUCLEO) & (R_a.tipo == "financiera")].shape[0]),
                                     "años_distintos_con_pico": int(R_a[R_a.pais.isin(NUCLEO)].pico.nunique())}
    DEST.mkdir(parents=True, exist_ok=True)
    pd.concat(et_a).to_parquet(DEST / "regimen_anual_dev.parquet")
    pd.concat(et_m).to_parquet(DEST / "regimen_mensual_dev.parquet")
    R_a.to_parquet(DEST / "recesiones_anuales_dev.parquet")
    pd.concat(rec_m).to_parquet(DEST / "giros_mensuales_dev.parquet")
    (REPO / "research" / "int" / "int1_resumen.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: res[k] for k in ("puerta_usa_nber", "euro_vs_cepr_media", "usa_anual_vs_nber_años",
                                          "episodios_nucleo_anual")}, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
