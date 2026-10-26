"""INT-0: matriz de cobertura del panel internacional (país × bloque × década). Solo cuenta observaciones; no mira
valores. Salida: research/int/cobertura.csv y research/int/cobertura.md.
Uso: .venv/bin/python -m scripts.int0_cobertura
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.warehouse import db

OUT = Path(__file__).resolve().parents[1] / "research" / "int"
JST = ["AUS", "BEL", "CAN", "CHE", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
# bloque → (regex de series_id con {c} = iso3 en minúsculas, frecuencia esperada)
BLOQUES = {
    "A_pib_real (JST)": (r"jst_{c}_rgdpmad", "A"), "A_ipc (JST)": (r"jst_{c}_cpi", "A"),
    "A_paro (JST)": (r"jst_{c}_unemp", "A"), "A_credito (JST)": (r"jst_{c}_tloans", "A"),
    "A_bolsa_tr (JST)": (r"jst_{c}_eq_tr", "A"), "A_bonos_tr (JST)": (r"jst_{c}_bond_tr", "A"),
    "A_letras (JST)": (r"jst_{c}_bill_rate", "A"), "A_vivienda_tr (JST)": (r"jst_{c}_housing_tr", "A"),
    "A_crisis (JST)": (r"jst_{c}_crisisjst", "A"),
    "M_bolsa_precio (OCDE)": (r"oecd_share_{c}", "M"), "M_bolsa_tr (AQR)": (r"aqr_mkt_{c}_m", "M"),
    "M_tipo_largo (OCDE)": (r"oecd_irlt_{c}", "M"), "M_tipo_3m (OCDE)": (r"oecd_ir3m_{c}", "M"),
    "M_tipo_oficial (BIS)": (r"bis_cbpol_{c2}", "M"), "M_cli (OCDE)": (r"oecd_cli_{c}", "M"),
    "M_paro (OCDE)": (r"oecd_unemp_{c}", "M"), "M_ipc (FMI IFS)": (r"imf_ifs_{c}_cpi_ix", "M"),
    "M_confianza_emp (OCDE)": (r"oecd_bci_{c}", "M"), "M_divisa (FMI IFS)": (r"imf_ifs_{c}_fx_usd_eop", "M"),
    "M_prod_industrial (OCDE)": (r"oecd_ip_{c}", "M"), "M_ventas_minoristas (OCDE)": (r"oecd_retail_{c}", "M"),
    "M_ipc (OCDE)": (r"oecd_cpi_{c}_\w+", "M"), "M_ipc_subyacente (OCDE)": (r"oecd_cpicore_{c}_\w+", "M"),
}
ISO2 = {"AUS": "au", "BEL": "be", "CAN": "ca", "CHE": "ch", "DEU": "de", "DNK": "dk", "ESP": "es", "FIN": "fi", "FRA": "fr",
        "GBR": "gb", "IRL": "ie", "ITA": "it", "JPN": "jp", "NLD": "nl", "NOR": "no", "PRT": "pt", "SWE": "se", "USA": "us"}


def main() -> None:
    con = db.connect(read_only=True)
    ids = set(db.all_series_ids(con))
    filas = []
    for c in JST:
        for bloque, (pat, _) in BLOQUES.items():
            rx = re.compile("^" + pat.format(c=c.lower(), c2=ISO2[c]) + "$")
            sids = sorted(i for i in ids if rx.match(i))
            if not sids:
                filas.append({"pais": c, "bloque": bloque, "series": "", "desde": None, "hasta": None, "obs": 0}); continue
            r = con.execute(f"select min(date), max(date), count(*) from obs_latest where series_id in ({','.join('?'*len(sids))})",
                            sids).fetchone()
            filas.append({"pais": c, "bloque": bloque, "series": ";".join(sids), "desde": str(r[0])[:7], "hasta": str(r[1])[:7], "obs": r[2]})
    con.close()
    df = pd.DataFrame(filas)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "cobertura.csv", index=False)
    tab = df.pivot(index="bloque", columns="pais", values="desde").fillna("—")
    falta = (df.groupby("bloque")["obs"].apply(lambda s: int((s == 0).sum()))).rename("países sin dato")
    full = tab.join(falta)
    md = ["| bloque | " + " | ".join(full.columns) + " |", "|---" * (len(full.columns) + 1) + "|"]
    md += [f"| {i} | " + " | ".join(str(v)[:4] if v != "—" else "—" for v in r) + " |" for i, r in full.iterrows()]
    (OUT / "cobertura.md").write_text("# Cobertura del panel internacional (INT-0)\n\nAño de inicio por país (— = no hay).\n\n"
                                      + "\n".join(md) + "\n")
    print(tab.join(falta).to_string())


if __name__ == "__main__":
    main()
