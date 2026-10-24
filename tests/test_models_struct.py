"""M2 `m2_struct_g` (docs/models/m2_structural_spec.md v1.2): solo datos SINTÉTICOS generados con el modelo de §3
(tests/m2_synth.py). Ninguna etiqueta ni dato real.

Controles de la spec §6 (en versión de test; la señal plantada completa con la cobertura del 80 % la publica
`src.models.m2_tools controls`): verosimilitud mínima = aumentada, recuperación de λ/φ/ρ, composición con oráculo =
código de la etiqueta, linealización de V_filtro frente al código exacto, PIT por truncamiento (3 cortes × 2 modos),
cadencia y arranque fijo (igualdad con una corrida que empieza en enero, N-4), regla de no convergencia, tabla v(edad).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from src.models import base as B
from src.models import harness as H
from src.models import models_struct as MS
from src.models import regime_components as C
from src.models import struct_factor as F
from tests.m2_synth import SCALE, TRUE, Synth, array_data


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("FKB_TRIALS_DIR", str(tmp_path / "trials"))
    monkeypatch.setenv("FKB_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FKB_TRIAL_LOG", str(tmp_path / "trial_log.md"))
    MS.clear_engines()
    yield
    MS.clear_engines()


@pytest.fixture(scope="module")
def syn():
    return Synth(7)


def _fit(m, s, T, **kw):
    info = s.info(T, **kw)
    m.fit_axis_continuous("G", None, None, None, None, info)
    return info


def test_minimal_and_augmented_likelihood_identical(syn):
    m = MS.StructuralG(rev="none")
    info = _fit(m, syn, "1990-01")
    v = m._v
    dev, _ = MS.dev_frame(syn.pit_levels(info["decision_calendar"][v.T])["levels"], info["features_history"], v.T,
                          m.cfg)
    X = MS.standardize(dev.loc[:v.T], v, m.cfg).to_numpy(float)
    a = F.loglike(X, m.cfg.kinds, v.params)
    b = F.loglike(X, m.cfg.kinds, v.params, augmented=True)
    assert np.isclose(a, b, rtol=0, atol=1e-6) and abs(a - b) / abs(a) < 1e-9
    assert F.FactorSSM(X, m.cfg.kinds, augmented=True).k_states == C.STRUCT.state_dim == 47
    assert F.FactorSSM(X, m.cfg.kinds).k_states == 13 + 6


def test_planted_signal_recovers_lambda_phi_rho(syn):
    m = MS.StructuralG(rev="none")
    _fit(m, syn, "2004-01")
    v = m._v
    assert v.converged
    cols = list(m.cfg.cols)
    lam = dict(zip(cols, v.params[:6]))
    true_x = {c: SCALE[c] * TRUE["lam"][c] / v.d[c] for c in MS.COINC}
    true_x["claims_4w_yoy"] = 10 * TRUE["lam"]["claims_4w_yoy"] / v.sd["claims_4w_yoy"]
    true_x["philly_neworders"] = 12 * TRUE["lam"]["philly_neworders"] / v.sd["philly_neworders"]
    for c in cols:
        assert abs(lam[c] - true_x[c]) < 0.12, (c, lam[c], true_x[c])
    assert lam["PAYEMS"] > 0 and lam["claims_4w_yoy"] < 0                      # normalización y signo esperado
    phi = v.params[6:8]
    assert abs(phi[0] - TRUE["phi"][0]) < 0.15 and abs(phi[1] - TRUE["phi"][1]) < 0.15
    rho = dict(zip(cols, v.params[8:14]))
    for c in cols:
        assert abs(rho[c] - TRUE["rho"][c]) < 0.15, (c, rho[c])


def test_composition_with_oracle_rates_is_label_code(syn):
    t = pd.Timestamp("1995-06-01")
    known = syn.pit_levels(syn.decision[t])["levels"]
    rhat = {}
    for c, lv in known.items():
        last = lv.index.max()
        fut = pd.date_range(last + pd.DateOffset(months=1), t + pd.DateOffset(months=4), freq="MS")
        rhat[c] = MS.rates(syn.levels[c]).reindex(fut)
    g = MS.compose_G(known, rhat, t)
    full = MS.label_G({c: v[v.index <= t + pd.DateOffset(months=4)] for c, v in syn.levels.items()})["G"][t]
    assert abs(g - full) < 1e-10


def test_vfiltro_linearization_matches_exact_label_code(syn):
    """∂Ĝ_t/∂r̂_{i,m} del código exacto ≈ c_{i,m} = (1/n)(2/3)w/σ_i (tolerancia 1 %; se ignora el efecto sobre la
    mediana de la tendencia y σ_i, declarado en la spec §4)."""
    t = pd.Timestamp("1997-03-01")
    known = syn.pit_levels(syn.decision[t])["levels"]
    base = {}
    for c, lv in known.items():
        fut = pd.date_range(lv.index.max() + pd.DateOffset(months=1), t + pd.DateOffset(months=4), freq="MS")
        base[c] = pd.Series(0.2, index=fut)
    g0 = MS.compose_G(known, base, t)
    ext = {c: MS.extend_level(known[c], base[c]) for c in known}
    ga = MS.label_G(ext)
    sig, n = ga.attrs["sigma"], int(ga["cobertura_g"][t])
    h = 1e-3
    for c in ("INDPRO", "CMRMTSPL"):
        for m in base[c].index:
            b2 = {k: v.copy() for k, v in base.items()}
            b2[c][m] += h
            dg = (MS.compose_G(known, b2, t) - g0) / h
            k = C.LABEL_PACE_OFFSETS.index((m.year - t.year) * 12 + m.month - t.month)
            assert np.isclose(dg, C.pace_rate_coeffs(sig[c], n)[k], rtol=1e-2), (c, m, dg)


@pytest.mark.parametrize("mode", ["vintage", "latest_truncated"])
def test_pit_by_truncation(mode):
    """Spec §6: la predicción en t no cambia si se alteran los niveles o las variables posteriores a la fecha de
    decisión (3 cortes × 2 modos)."""
    tab = {"v": {"INDPRO": {k: 0.4 for k in C.STRUCT.rev_age_buckets},
                 "PAYEMS": {k: 0.02 for k in C.STRUCT.rev_age_buckets}},
           "rho_bar": {k: 0.6 for k in C.STRUCT.rev_age_buckets},
           "var_r": {"INDPRO": 0.5, "PAYEMS": 0.04, "W875RX1": 0.3, "CMRMTSPL": 1.0}}
    fv = mode == "vintage"

    def wrap(s):
        orig = s.pit_levels

        def f(date):
            o = orig(date)
            return {"levels": o["levels"], "from_vintage": {k: fv for k in o["levels"]}}
        return f
    for t in ("1988-01", "1995-01", "2002-01"):
        t = pd.Timestamp(t + "-01")
        a, b = Synth(3), Synth(3)
        later = t + pd.DateOffset(months=1)
        for c in b.levels:
            b.levels[c] = b.levels[c].where(b.levels[c].index < later, b.levels[c] * 1.3)
        b.X.loc[b.X.index > t] = -b.X.loc[b.X.index > t]
        outs = []
        for s, key in ((a, "a"), (b, "b")):
            s.pit_levels = wrap(s)
            MS.clear_engines()
            m = MS.StructuralG(rev_table=tab)
            info = s.info(t, data_key=key, mode=mode)
            m.fit_axis_continuous("G", None, None, None, None, info)
            outs.append(m.predict_axis_continuous("G", pd.DataFrame(index=[t]), info))
        assert outs[0][0][0] == outs[1][0][0] and outs[0][1][0] == outs[1][1][0]
        if fv:
            assert m.nowcast(t, info)["V_rev"] > 0


def test_reestimation_schedule_fixed_start_and_dry_run_equality(syn):
    """Primer corte + cada enero; arranque fijo ⇒ una corrida que empieza en enero (ensayo en seco) da en cada enero
    los mismos parámetros que la que empezó antes, en las reestimaciones con fit_converged = true (N-4)."""
    a = MS.StructuralG(rev="none")
    for T in ("1985-07", "1985-08", "1986-01", "1986-02", "1987-01"):
        _fit(a, syn, T)
    assert [h["T"] for h in a._hist] == ["1985-07", "1986-01", "1987-01"]
    MS.clear_engines()
    b = MS.StructuralG(rev="none")
    for T in ("1986-01", "1987-01"):
        _fit(b, syn, T)
    for ha, hb in zip(a._hist[1:], b._hist):
        assert ha["fit_converged"] and hb["fit_converged"]
    assert np.array_equal(a._v.params, b._v.params) and a._v.d == b._v.d
    assert a.coefficients()["G:fit_converged"] == 1.0


def test_nonconvergence_keeps_previous_version(syn, monkeypatch):
    real = F.fit_ml
    calls = {"n": 0}

    def fake(*a, **k):
        p, _, info = real(*a, **k)
        calls["n"] += 1
        return p, False, info
    monkeypatch.setattr(F, "fit_ml", fake)
    m = MS.StructuralG(rev="none")
    _fit(m, syn, "1990-01")
    v1 = m._v
    assert not v1.converged and not v1.kept_previous            # primera: punto final del optimizador
    _fit(m, syn, "1991-01")
    assert m._v.kept_previous and np.array_equal(m._v.params, v1.params) and m._v.d == v1.d
    assert m._v.from_T == v1.T and np.isfinite(m._v.v_tend)
    d = m.diagnostics()
    assert d["sin_convergencia"] == 2 and d["reestimaciones"][1]["conserva_anterior"] is True


def test_revision_table_rules():
    assert [MS.age_bucket(a) for a in (1, 6, 7, 12, 13, 400)] == ["1", "6", "7-12", "7-12", ">=13", ">=13"]
    errs = {"INDPRO": pd.DataFrame({"age": [1] * 40 + [2] * 10 + [13] * 35, "err": [1.0] * 40 + [3.0] * 10 + [2.0] * 35}),
            "PAYEMS": pd.DataFrame({"age": [1] * 5, "err": [0.5] * 5})}
    var = {"INDPRO": 2.0, "PAYEMS": 1.0, "W875RX1": 4.0}
    t = MS.summarize_rev(errs, var, min_pairs=30)
    assert t["v"]["INDPRO"]["1"] == 1.0 and t["v"]["INDPRO"]["2"] == 1.0          # < 30 pares → el tramo más joven
    assert t["v"]["INDPRO"][">=13"] == 4.0
    assert np.isnan(t["v"]["PAYEMS"]["1"])                                       # ningún tramo con ≥ 30 → NaN …
    assert MS.rev_var(t, "PAYEMS", 1) == 0.0                                     # … y V_rev = 0
    t2 = MS.summarize_rev(errs, var)
    assert t2["v"]["INDPRO"]["2"] == 9.0
    assert np.isclose(MS.rev_var(t2, "W875RX1", 1), t2["rho_bar"]["1"] * 4.0)   # sin vintages ≤ 2004: ρ̄·Var(r)
    assert np.isclose(t2["rho_bar"]["1"], np.mean([1.0 / 2.0, 0.25 / 1.0]))


def test_m2_and_variants_run_in_harness(syn):
    """Integración con el arnés v2.4 (ArrayData sintético): g_mu/g_sd, P = Φ(μ/√(σ² + s_G²)), eje I = M0,
    coeficientes y diagnóstico de convergencia; las variantes corren."""
    data = array_data(syn)
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence,
           "m2_struct_g": lambda **k: MS.StructuralG(rev="none", **k),
           "m2_struct_g_coinc": MS.REGISTRY["m2_struct_g_coinc"], "m2_struct_g_ar1": MS.REGISTRY["m2_struct_g_ar1"],
           "m2_struct_g_platt": lambda **k: _platt_norev(**k)}
    cfg = H.HarnessConfig(name="m2t", models=tuple(reg), modes=("synthetic",), test_start="1990-01",
                          test_end="1990-03", baseline="m0_calibrated_persistence", epochs=(),
                          min_train_recessions=0, min_train_g_changes=0)
    r = H.run(cfg, registry=reg, datas={"synthetic": data}, record=False)
    P = r["preds"].set_index(["model", "month"])
    g = P.loc["m2_struct_g"]
    pg = g["p_expansion"] + g["p_late_cycle"]
    assert np.allclose(pg, norm.cdf(g["g_mu"] / np.sqrt(g["g_sd"] ** 2 + 0.4 ** 2)))
    i_m0 = P.loc["m0_calibrated_persistence"][["p_late_cycle", "p_stagflation"]].sum(axis=1)
    assert np.allclose(g[["p_late_cycle", "p_stagflation"]].sum(axis=1), i_m0)
    assert r["report"]["diagnostico_ajuste"]["synthetic/m2_struct_g"]["sin_convergencia"] == 0
    c = [x["coef"] for x in r["diag"]["synthetic"] if x["model"] == "m2_struct_g_ar1" and x.get("coef")][-1]
    assert "G:phi2" not in c and "G:phi1" in c
    c = [x["coef"] for x in r["diag"]["synthetic"] if x["model"] == "m2_struct_g_coinc" and x.get("coef")][-1]
    assert "G:lambda_claims_4w_yoy" not in c
    assert {"m2_struct_g_platt", "m2_struct_g_coinc", "m2_struct_g_ar1"} <= set(P.index.get_level_values(0))


def _platt_norev(**k):
    m = MS.StructuralGPlatt(**k)
    m._m2 = MS.StructuralG(rev="none", philly_pre1990_nan=k.get("philly_pre1990_nan", False))
    return m


def test_philly_flag_blanks_pre_1990_07(syn):
    cfg = MS.StructCfg(philly_pre1990_nan=True)
    dev, _ = MS.dev_frame(syn.pit_levels(syn.decision[pd.Timestamp("1995-01-01")])["levels"], syn.X,
                          pd.Timestamp("1995-01-01"), cfg)
    assert dev.loc[:"1990-06", "philly_neworders"].isna().all() and dev.loc["1990-07":"1995-01", "philly_neworders"].notna().all()
    dev2, _ = MS.dev_frame(syn.pit_levels(syn.decision[pd.Timestamp("1995-01-01")])["levels"], syn.X,
                           pd.Timestamp("1995-01-01"), MS.StructCfg())
    assert dev2.loc["1968-06":"1990-06", "philly_neworders"].notna().all()
    assert dev2.loc["1995-02":, "philly_neworders"].isna().all()                # nada posterior al mes de decisión
