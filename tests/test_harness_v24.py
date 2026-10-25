"""Arnés v2.4 (docs/models/harness.md §11 v2.4) y pool (docs/models/pool_spec.md v1.2): solo datos SINTÉTICOS
(ArrayData). Ninguna etiqueta real.

- criterio 8 (Validador N-5): el denominador son TODOS los cortes de la ventana; cortes sin coeficientes y γ = 0
  dan `criterio_fraccion_cumple = false` (mientras `criterio_signos_cumple` sale True de forma vacía);
- niveles PIT con barrera de fecha; historia de variables acotada; calendario de decisiones;
- modelo apilado: recibe las P(G) fuera de muestra producidas en el corte de cada mes; antes de N_min el pool es M0
  bit a bit;
- herencia de la marca de S-PIT-001 (N-6);
- informe: sd_mensual y ACF 1-24, 3 m × 80/20, estudio de eventos;
- controles sintéticos del pool (i)-(v) de pool_spec.md §5.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from src.models import base as B
from src.models import harness as H
from src.models import metrics as M
from src.models import models_pool as MP
from src.models import regime_components as C
from src.models.metrics import P_COLS, QUADS


@pytest.fixture(autouse=True)
def trial_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("FKB_TRIALS_DIR", str(tmp_path / "trials"))
    monkeypatch.setenv("FKB_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FKB_TRIAL_LOG", str(tmp_path / "trial_log.md"))


def _target(n=420, seed=0, start="1960-01"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start + "-01", periods=n, freq="MS")
    G = np.zeros(n)
    for t in range(1, n):
        G[t] = 0.95 * G[t - 1] + 0.35 * rng.standard_normal()
    pg = norm.cdf(G / 0.4)
    P = np.column_stack([pg * 0.7, pg * 0.3, (1 - pg) * 0.3, (1 - pg) * 0.7])
    t = pd.DataFrame(P, index=idx, columns=P_COLS)
    t["label_hard"] = [QUADS[i] for i in P.argmax(axis=1)]
    t["usrec"] = (G < -0.8).astype(float)
    t["weight"], t["provisional"], t["G"] = 1.0, False, G
    return t


def _data(tgt, seed=1, levels_fn=None):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"x": rng.standard_normal(len(tgt)), "y": rng.standard_normal(len(tgt))}, index=tgt.index)
    ci = {c: {"estado": "principal", "start": X.index.min()} for c in X.columns}
    return H.ArrayData(X, tgt, ci, kind="synthetic", mode="synthetic", levels_fn=levels_fn)


def _cfg(models, **kw):
    base = dict(name="t24", models=tuple(models), modes=("synthetic",), test_start="1975-01", test_end="1989-12",
                refit_every=1, baseline=models[0], epochs=(), min_train_recessions=0, min_train_g_changes=0,
                min_train_months=60)
    base.update(kw)
    return H.HarnessConfig(**base)


class GammaStub(B.AxisModel):
    """Expone coeficientes G:gamma1…4 fijos (persistencia calibrada por eje)."""
    name = "gamma_stub"
    uses_persistence = True
    axis_features = {"G": ("x",), "I": ()}

    def __init__(self, gammas=(0.0, 0.0, 0.0, 0.0)):
        self.g = gammas
        self.m0 = B.CalibratedPersistence()

    def fit_axis(self, axis, X, t, w, info):
        self.m0.fit_axis(axis, X, t, w, info)

    def predict_axis(self, axis, X, info):
        return self.m0.predict_axis(axis, X, info)

    def coefficients(self):
        return {f"G:gamma{j + 1}": float(v) for j, v in enumerate(self.g)}


SF = {"gamma_stub": {"coefs": list(C.TVTP.sign_coefs), "threshold": 0.01, "min_frac": 0.5,
                     "missing_counts_as_fail": True}}
EXP = {"gamma_stub": {k: {"signo": "+", "decide": False} for k in C.TVTP.sign_coefs}}


@pytest.mark.usefixtures("synthetic_label_meta")
def test_N5_all_gamma_zero_fails_criterion8_while_old_key_is_vacuous():
    tgt = _target()
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, "gamma_stub": lambda: GammaStub((0, 0, 0, 0))}
    cfg = _cfg(list(reg), test_end="1979-12", sign_fraction=SF, expected_signs=EXP)
    r = H.run(cfg, registry=reg, datas={"synthetic": _data(tgt)}, record=False)
    s = r["report"]["signos_coeficientes"]["synthetic/gamma_stub"]
    assert s["criterio_fraccion_cumple"] is False
    assert all(v["n_cortes"] == 60 and v["frac"] == 0.0 for v in s["fraccion_umbral"].values())
    assert s["criterio_signos_cumple"] is True          # vacío: todos decide: false (A3-8 lo excluye)
    assert "NO es el criterio 8" in s["nota_criterio_signos_cumple"]


def test_N5_denominator_is_every_cut_of_the_window_not_the_fitted_ones():
    """Cortes sin ajuste (eje G omitido) cuentan como no cumplidos: con la mitad omitidos y γ = 0,5 la fracción es
    0,5 (cumple justo) y con la ventana partida no puede salir de los cortes ajustados (sería 1,0)."""
    dl = []
    cuts = pd.date_range("1980-01-01", periods=10, freq="MS")
    for i, m in enumerate(cuts):
        ok = i % 2 == 0
        dl.append({"model": "gamma_stub", "refit_month": m, "coef": {f"G:gamma{j}": 0.5 for j in range(1, 5)},
                   "ejes": {"G": {"n_train": 1} if ok else {"skipped": True}, "I": {}}, **({} if ok else {"skipped": True})})
    cfg = _cfg(["m0_calibrated_persistence", "gamma_stub"], test_start="1980-01", test_end="1980-10")
    r = H.sign_fraction_report(dl, "gamma_stub", SF["gamma_stub"], cfg)
    assert all(v["n_cortes"] == 10 and v["n_sin_coef"] == 5 and v["frac"] == 0.5 for v in r["fraccion_umbral"].values())
    assert r["criterio_fraccion_cumple"] is True
    dl[0]["coef"] = {f"G:gamma{j}": 0.0 for j in range(1, 5)}
    assert H.sign_fraction_report(dl, "gamma_stub", SF["gamma_stub"], cfg)["criterio_fraccion_cumple"] is False
    assert len(H.cut_months(cfg)) == 10
    assert len(H.cut_months(_cfg(["a"], baseline="a", test_start="1980-01", test_end="1981-12", refit_every=12,
                                 eval_window=("1980-06", "1981-12")))) == 1
    with pytest.raises(ValueError):
        H.sign_fraction_report(dl, "gamma_stub", {**SF["gamma_stub"], "missing_counts_as_fail": False}, cfg)


@pytest.mark.usefixtures("synthetic_label_meta")
def test_N5_stale_coefficients_of_a_skipped_cut_do_not_count():
    """`coefficients()` devuelve los del corte anterior cuando se omite el eje: el arnés no debe contarlos."""
    tgt = _target()
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, "gamma_stub": lambda: GammaStub((1, 1, 1, 1))}
    cfg = _cfg(list(reg), test_end="1976-12", sign_fraction=SF, min_train_months=60)
    data = _data(tgt)
    r = H.run(cfg, registry=reg, datas={"synthetic": data}, record=False)
    s = r["report"]["signos_coeficientes"]["synthetic/gamma_stub"]["fraccion_umbral"]["G:gamma1"]
    assert s["n_cortes"] == 24 and s["frac"] == 1.0
    dl = r["diag"]["synthetic"]
    for x in dl:
        if x["model"] == "gamma_stub" and x.get("refit_month") is not None and x["refit_month"].month % 2:
            x["ejes"]["G"]["skipped"] = True
    rr = H.sign_fraction_report(dl, "gamma_stub", SF["gamma_stub"], cfg)
    assert rr["fraccion_umbral"]["G:gamma1"]["frac"] == 0.5


# ------------------------------------------------------------------ niveles PIT e historia
class LevelsSpy(B.AxisModel):
    name = "levels_spy"
    uses_persistence = True
    uses_pit_levels = True
    axis_features = {"G": ("x",), "I": ()}

    def __init__(self, ask_after=0):
        self.ask_after, self.seen = ask_after, []
        self.m0 = B.CalibratedPersistence()

    def fit_axis(self, axis, X, t, w, info):
        if axis == "G":
            fh = info["features_history"]
            self.seen.append(("fit", info["refit_month"], fh.index.max(), info["decision_calendar"].index.max()))
            info["pit_levels"](info["decision_date"] + pd.DateOffset(days=self.ask_after))
        self.m0.fit_axis(axis, X, t, w, info)

    def predict_axis(self, axis, X, info):
        if axis == "G":
            self.seen.append(("pred", X.index.max(), info["features_history"].index.max(),
                              list(info["decision_dates"].index)))
            for m, d in info["decision_dates"].items():
                info["pit_levels"](d)
        return self.m0.predict_axis(axis, X, info)


@pytest.mark.usefixtures("synthetic_label_meta")
def test_pit_levels_barrier_and_bounded_history():
    tgt = _target()
    calls = []
    lf = lambda d: calls.append(pd.Timestamp(d)) or {"levels": {}, "from_vintage": {}}  # noqa: E731
    spy = LevelsSpy()
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, "levels_spy": lambda: spy}
    cfg = _cfg(list(reg), test_end="1977-12", refit_every=12)
    H.run(cfg, registry=reg, datas={"synthetic": _data(tgt, levels_fn=lf)}, record=False)
    fits = [s for s in spy.seen if s[0] == "fit"]
    preds = [s for s in spy.seen if s[0] == "pred"]
    assert all(fh == m0 and dc == m0 for _, m0, fh, dc in fits)            # fit: nada posterior al corte
    assert all(fh == mx for _, mx, fh, _ in preds)                          # predicción: hasta su última fila
    assert len(calls) == 3 + 36
    bad = LevelsSpy(ask_after=1)
    with pytest.raises(H.HoldoutLocked):
        H.run(_cfg(["m0_calibrated_persistence", "levels_spy"], test_end="1975-12"),
              registry={"m0_calibrated_persistence": B.CalibratedPersistence, "levels_spy": lambda: bad},
              datas={"synthetic": _data(tgt, levels_fn=lf)}, record=False)


def test_m2_flag_inheritance_N6():
    class Dep(B.AxisModel):
        m2_dependent = True

        def __init__(self, philly_pre1990_nan=False):
            self.flag = philly_pre1990_nan
    cfg = _cfg(["a", "b"], baseline="a", model_params={"m2_struct_g": {"philly_pre1990_nan": True}})
    assert H.model_kwargs(cfg, "b", Dep) == {"philly_pre1990_nan": True}
    assert H.model_kwargs(cfg, "a", B.CalibratedPersistence) == {}
    bad = _cfg(["a", "b"], baseline="a", model_params={"m2_struct_g": {"philly_pre1990_nan": True},
                                                       "b": {"philly_pre1990_nan": False}})
    with pytest.raises(ValueError):
        H.model_kwargs(bad, "b", Dep)
    assert H.model_kwargs(_cfg(["a"], baseline="a"), "b", Dep) == {"philly_pre1990_nan": False}
    reg = H.model_registry()
    for n in ("m3_tvtp_g", "m3_ctp_g", "pool_g", "pool_g_kull", "m2_struct_g_platt", "m2_struct_g_ar1",
              "m3_tvtp_g_fac"):
        assert H.model_kwargs(cfg, n, reg[n]) == {"philly_pre1990_nan": True}, n


# ------------------------------------------------------------------ modelo apilado
class FixedG(B.AxisModel):
    """Componente de juguete: P(G) = Φ(G_verdadero/0,4 + ruido) (o constante si `const`)."""
    uses_persistence = True
    axis_features = {"G": (), "I": ()}

    def __init__(self, name, noise=0.0, const=None, seed=0, src=None):
        self.name, self.noise, self.const, self.src = name, noise, const, src
        self.rng = np.random.default_rng(seed)
        self.m0 = B.CalibratedPersistence()

    def fit_axis(self, axis, X, t, w, info):
        self.m0.fit_axis(axis, X, t, w, info)

    def predict_axis(self, axis, X, info):
        if axis == "I":
            return self.m0.predict_axis(axis, X, info)
        if self.const is not None:
            return np.full(len(X), self.const)
        z = self.src.reindex(X.index).to_numpy() / 0.4 + self.noise * self.rng.standard_normal(len(X))
        return norm.cdf(z)


class PoolSpy(MP.PoolG):
    seen: list = []

    def fit_axis(self, axis, X, t, w, info):
        if axis == "G":
            sp = info["stack_preds"]
            PoolSpy.seen.append((info["refit_month"], sp.index.max(), X.index.max(),
                                 {c: sp[f"{c}@corte"].dropna() for c in self.components}))
        super().fit_axis(axis, X, t, w, info)


def _pool_reg(tgt, pool_cls=MP.PoolG, m2=None, m3=None):
    return {"m0_calibrated_persistence": B.CalibratedPersistence,
            "m2_struct_g": lambda **k: m2 or FixedG("m2_struct_g", noise=0.0, src=tgt["G"]),
            "m3_tvtp_g": lambda **k: m3 or FixedG("m3_tvtp_g", noise=2.0, seed=3, src=tgt["G"]),
            "pool_g": lambda **k: pool_cls(name="pool_g")}


@pytest.mark.usefixtures("synthetic_label_meta")
def test_stacked_gets_out_of_sample_preds_from_their_cut_and_is_m0_before_nmin():
    tgt = _target(n=480)
    PoolSpy.seen = []
    reg = _pool_reg(tgt, pool_cls=PoolSpy)
    cfg = _cfg(["pool_g", "m0_calibrated_persistence", "m2_struct_g", "m3_tvtp_g"],
               baseline="m0_calibrated_persistence", test_start="1972-01", test_end="1981-12", refit_every=12)
    r = H.run(cfg, registry=reg, datas={"synthetic": _data(tgt)}, record=False)
    for m0, spmax, trmax, cuts in PoolSpy.seen:
        assert spmax <= m0 and trmax <= m0 - pd.DateOffset(months=6)
        for c, s in cuts.items():
            assert all(cut <= m < cut + pd.DateOffset(months=12) for m, cut in s.items())
    P = r["preds"].set_index(["model", "month"])
    early = [m for m in P.loc["pool_g"].index if m < pd.Timestamp("1977-01-01")]
    assert early
    a, b = P.loc["pool_g"].loc[early, P_COLS], P.loc["m0_calibrated_persistence"].loc[early, P_COLS]
    assert (a.to_numpy() == b.to_numpy()).all()                               # (v) bit a bit
    co = {x["refit_month"]: x["coef"] for x in r["diag"]["synthetic"] if x["model"] == "pool_g" and x.get("coef")}
    assert co[pd.Timestamp("1976-01-01")]["G:n_est"] < 60 and co[pd.Timestamp("1980-01-01")]["G:n_est"] >= 60
    # (i) con un oráculo y dos ruidosos, el peso va al oráculo
    c81 = co[pd.Timestamp("1981-01-01")]
    assert c81["G:w_m2"] > 0.4 and c81["G:w_m3"] < 0.25 and c81["G:w_m2"] > co[pd.Timestamp("1978-01-01")]["G:w_m2"]
    rng = np.random.default_rng(1)                                                # (i) con muestra larga: → oráculo
    n = 3000
    tt = rng.uniform(0.02, 0.98, n)
    P = np.column_stack([np.clip(tt + rng.normal(0, .3, n), .01, .99), tt, np.clip(tt + rng.normal(0, .3, n), .01, .99)])
    st, ok = MP.fit_pool(P, tt, np.ones(n))
    assert ok and st["w"][1] > 0.8 and st["w"][1] > 3 * max(st["w"][0], st["w"][2])
    with pytest.raises(ValueError):
        H.run(_cfg(["pool_g", "m0_calibrated_persistence"], baseline="m0_calibrated_persistence"),
              registry=reg, datas={"synthetic": _data(tgt)}, record=False)


def test_pool_uninformative_components_follow_prior_and_underdispersed_gets_a_b_above_1():
    rng = np.random.default_rng(0)
    n = 300
    t = np.full(n, 0.5)                                       # objetivo blando sin información
    p0 = np.full(n, 0.5)
    P = np.column_stack([p0, np.full(n, 0.5), np.full(n, 0.5)])
    st, ok = MP.fit_pool(P, t, np.ones(n))
    assert ok and np.allclose(st["w"], C.POOL.prior_mode, atol=0.02)          # (ii)
    assert np.allclose(C.blp_transform(P @ st["w"], st["a"], st["b"]), 0.5, atol=0.02)
    # (iii) pool infradispersado conocido: la verdad es B_{2,2}(p) sobre un pool lineal
    q = rng.uniform(0.05, 0.95, n)
    y = (rng.uniform(size=(20, n)) < C.blp_transform(q, 2.5, 2.5)).astype(float).mean(axis=0)
    P = np.column_stack([q, q, q])
    st, ok = MP.fit_pool(P, y, np.ones(n) * 20)
    assert st["a"] > 1.3 and st["b"] > 1.3


def test_pool_weights_ignore_months_after_the_embargo():
    """(iv) PIT: cambiar p_k,s o la etiqueta de meses s > m0 − 6 no cambia los pesos de m0 (el modelo solo ve las
    filas de entrenamiento que da el arnés; aquí se comprueba con la API del modelo)."""
    rng = np.random.default_rng(2)
    idx = pd.date_range("1980-01-01", periods=120, freq="MS")
    sp = pd.DataFrame({c: rng.uniform(0.05, 0.95, 120) for c in C.POOL.components}, index=idx)
    t = (rng.uniform(size=114) < sp.iloc[:114, 1]).astype(float).to_numpy()
    X = pd.DataFrame(index=idx[:114])
    m0 = idx[-1]
    a = MP.PoolG()
    a.fit_axis("G", X, t, np.ones(114), {"stack_preds": sp, "refit_month": m0})
    sp2 = sp.copy()
    sp2.iloc[114:] = 0.99
    b = MP.PoolG()
    b.fit_axis("G", X, t, np.ones(114), {"stack_preds": sp2, "refit_month": m0})
    assert np.array_equal(a.state["w"], b.state["w"]) and a.state["a"] == b.state["a"]


def test_pool_variants_and_coefficients():
    rng = np.random.default_rng(4)
    idx = pd.date_range("1980-01-01", periods=100, freq="MS")
    sp = pd.DataFrame({c: rng.uniform(0.05, 0.95, 100) for c in C.POOL.components}, index=idx)
    t = (rng.uniform(size=100) < sp.iloc[:, 0]).astype(float).to_numpy()
    X = pd.DataFrame(index=idx)
    info = {"stack_preds": sp, "refit_month": idx[-1]}
    for name, fn in MP.REGISTRY.items():
        m = fn()
        m.fit_axis("G", X, t, np.ones(100), info)
        p = m.predict_axis("G", X, info)
        assert p.shape == (100,) and np.isfinite(p).all() and (p > 0).all() and (p < 1).all()
        c = m.coefficients()
        assert {"G:w_m0", "G:w_m2", "G:w_m3", "G:blp_a", "G:blp_b", "G:n_est"} <= set(c)
        assert np.isclose(c["G:w_m0"] + c["G:w_m2"] + c["G:w_m3"], 1.0)
    eq = MP.REGISTRY["pool_g_eq"]()
    eq.fit_axis("G", X, t, np.ones(100), info)
    assert np.allclose(eq.predict_axis("G", X, info), sp.to_numpy().mean(axis=1))


# ------------------------------------------------------------------ informe
def test_d_dispersion_acf():
    rng = np.random.default_rng(0)
    e = rng.standard_normal(2000)
    x = np.zeros(2000)
    for i in range(1, 2000):
        x[i] = 0.8 * x[i - 1] + e[i]
    o = M.d_dispersion(x)
    assert len(o["acf_1_24"]) == 24 and abs(o["acf_1_24"][0] - 0.8) < 0.05 and abs(o["acf_1_24"][1] - 0.64) < 0.07
    assert np.isclose(o["sd_mensual"], x.std(ddof=1))


def test_declared_8020_and_event_study():
    idx = pd.date_range("1980-01-01", periods=60, freq="MS")
    g = np.r_[np.ones(20), np.zeros(20), np.ones(20)]
    lab = pd.DataFrame({"p_g_high": g, "label_hard": np.where(g > 0, "expansion", "low_growth_disinfl")}, index=idx)
    pg = pd.Series(np.r_[np.full(21, 0.9), np.full(19, 0.1), np.full(20, 0.9)], index=idx)
    pg.iloc[50:53] = 0.1                                       # declaraciones falsas: G bajo en 1984-05, alto en 1984-08
    o = M.declared_detection_8020(pg, lab)
    assert o["n_giros"] == 2 and o["declarados"] == 2
    assert [r["retraso"] for r in o["giros"]] == [3, 2]
    assert [d["mes"] for d in o["declaraciones"]] == ["1981-12", "1983-07", "1984-05", "1984-08"]
    assert o["declarados_falsos"] == 2 and np.isclose(o["declarados_falsos_por_año"], 2 / 5)
    d = pd.Series(np.arange(60, dtype=float), index=idx)
    st = pd.Series(True, index=idx)
    es = M.event_study(d, lab, st)
    e0 = es["episodios"][0]
    assert e0["sentido"] == "A→B" and e0["entrada_salida"] == np.mean([20, 21, 22, 23, 24])
    assert e0["antes"] == np.mean(range(14, 20)) and e0["despues"] == np.mean(range(25, 29))
    assert es["media_por_sentido"]["B→A"]["n_episodios"] == 1 and es["estables"]["n"] == 60


@pytest.mark.usefixtures("synthetic_label_meta")
def test_report_has_v24_keys_for_all_comparisons():
    tgt = _target()
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, "climatology": B.Climatology}
    r = H.run(_cfg(list(reg), test_end="1980-12"), registry=reg, datas={"synthetic": _data(tgt)}, record=False)
    c = r["report"]["frente_al_baseline"]["synthetic/climatology"]
    assert "sd_mensual" in c["mejora_logloss"] and len(c["mejora_logloss"]["acf_1_24"]) == 24
    assert "mejora_logloss_b24" in c
    assert set(r["report"]["deteccion_declarada_8020"]) == {"synthetic/m0_calibrated_persistence",
                                                            "synthetic/climatology"}
    assert "synthetic/climatology" in r["report"]["estudio_eventos"]
