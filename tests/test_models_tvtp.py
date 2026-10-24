"""M3 `m3_tvtp_g` / `m3_ctp_g` (docs/models/m3_tvtp_spec.md v1.2): solo datos SINTÉTICOS. Controles de la spec §5:
señal plantada (γ conocidos), ruido (los γ se encogen y TVTP no mejora a CTP), PIT por truncamiento del filtro
anclado, anidamiento, y emisión = Ĝ de M2 en el mes de la fila (motor compartido)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import base as B
from src.models import harness as H
from src.models import models_struct as MS
from src.models import models_tvtp as MT
from tests.m2_synth import Synth, array_data

GTRUE = (1.0, 0.5, 0.5, 1.0)


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("FKB_TRIALS_DIR", str(tmp_path / "trials"))
    monkeypatch.setenv("FKB_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FKB_TRIAL_LOG", str(tmp_path / "trial_log.md"))
    MS.clear_engines()
    yield
    MS.clear_engines()


def simulate(n=600, seed=0, gammas=GTRUE, z_informative=True, aA=-3.0, aB=-2.0, muA=0.6, muB=-0.9, om=1.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1950-01-01", periods=n, freq="MS")
    z = rng.standard_normal((n, 3))
    S = np.zeros(n, int)
    S[0] = 1
    for s in range(1, n):
        zz = z[s] if z_informative else np.zeros(3)
        if S[s - 1] == 1:
            p = MT._sig(aA - gammas[0] * zz[0] + gammas[1] * zz[1])
            S[s] = 0 if rng.uniform() < p else 1
        else:
            p = MT._sig(aB - gammas[2] * zz[1] + gammas[3] * zz[2])
            S[s] = 1 if rng.uniform() < p else 0
    x = np.where(S == 1, muA, muB) + om * rng.standard_normal(n)
    t = np.where(S == 1, 0.9, 0.1)
    Z = pd.DataFrame(z, index=idx, columns=list(MT.TRANS))
    pers = pd.Series(t, index=idx).shift(5)
    X = Z.assign(claims_4w_yoy=0.0, philly_neworders=0.0, pers_axis_growth=pers,
                 pers_label_month=idx - pd.DateOffset(months=5))
    return X.iloc[5:], pd.Series(t, index=idx).iloc[5:], pd.Series(x, index=idx), S


class SynthTVTP(MT.TVTPG):
    """TVTPG con la emisión SINTÉTICA (sin factor): solo para probar la parte de Markov."""

    def __init__(self, x, **kw):
        super().__init__(**kw)
        self._x = x

    def _ensure_version(self, info):
        return None

    def _emission(self, eng, months, info):
        return self._x.reindex(pd.DatetimeIndex(months)).to_numpy(float)


def _info(X, x):
    return {"features_history": X[list(MT.TRANS)], "refit_month": X.index[-1]}


def _ll(p, t):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(t * np.log(p) + (1 - t) * np.log(1 - p)).mean())


def test_planted_signal_recovers_sign_and_magnitude():
    X, t, x, _ = simulate(n=600, seed=11)
    m = SynthTVTP(x)
    m.fit_axis("G", X, t.to_numpy(), np.ones(len(X)), _info(X, x))
    g = [m.par[f"gamma{j}"] for j in range(1, 5)]
    for est, tru in zip(g, GTRUE):
        assert est > 0.1 and tru / 4 < est < tru * 2.5, (g, GTRUE)
    assert m.par["mu_A"] > m.par["mu_B"] and 0.5 < np.sqrt(m.par["omega2"]) < 1.5
    c = m.coefficients()
    assert {"G:alpha_A", "G:alpha_B", "G:gamma1", "G:gamma4", "G:mu_A", "G:mu_B", "G:omega", "G:cal_c",
            "G:cal_b"} <= set(c)


def test_noise_transitions_shrink_and_do_not_beat_ctp():
    """Con z sin relación con las transiciones: γ → 0 y ll(TVTP) ≤ ll(CTP) + 0,005 en la media de 20 semillas
    (fuera de muestra: entrena en 400 meses, puntúa los 195 siguientes con su ancla)."""
    d, gs = [], []
    for seed in range(20):
        X, t, x, _ = simulate(n=600, seed=100 + seed, z_informative=False)
        tr, te = X.iloc[:400], X.iloc[400:]
        out = []
        for ctp in (False, True):
            m = SynthTVTP(x, constant_transitions=ctp)
            m.fit_axis("G", tr, t.iloc[:400].to_numpy(), np.ones(400), _info(X, x))
            p = m.predict_axis("G", te, _info(X, x))
            out.append(_ll(p, (t.iloc[400:] > 0.5).astype(float).to_numpy()))
            if not ctp:
                gs.append([m.par[f"gamma{j}"] for j in range(1, 5)])
            else:
                assert all(m.par[f"gamma{j}"] == 0 for j in range(1, 5))
        d.append(out[0] - out[1])
    assert np.mean(d) <= 0.005, np.mean(d)
    assert np.mean(gs) < 0.15


def test_anchored_filter_pit_truncation_and_nesting():
    X, t, x, _ = simulate(n=300, seed=5)
    m = SynthTVTP(x)
    m.fit_axis("G", X.iloc[:250], t.iloc[:250].to_numpy(), np.ones(250), _info(X, x))
    row = X.iloc[[260]]
    p1 = m.predict_axis("G", row, _info(X, x))
    X2, x2 = X.copy(), x.copy()
    X2.iloc[261:, :3] = 99.0
    x2.iloc[x2.index > row.index[0]] = -99.0
    m._x = x2
    assert m.predict_axis("G", row, _info(X2, x2))[0] == p1[0]
    # anidamiento: γ = 0 y emisión plana → propagación de la persistencia h pasos con transiciones constantes
    par = {"alpha_A": -2.0, "alpha_B": -1.5, "gamma1": 0.0, "gamma2": 0.0, "gamma3": 0.0, "gamma4": 0.0,
           "mu_A": 0.3, "mu_B": 0.3, "omega2": 1.0}
    pa, h = 0.8, 5
    zs, xs = np.random.default_rng(0).standard_normal((h, 3)), np.random.default_rng(1).standard_normal(h)
    q = MT.anchored_filter(pa, zs, xs, par, 1 / 3)
    Tm = np.array([[1 - MT._sig(-2.0), MT._sig(-2.0)], [MT._sig(-1.5), 1 - MT._sig(-1.5)]])
    assert np.isclose(q, (np.array([pa, 1 - pa]) @ np.linalg.matrix_power(Tm, h))[0])


def test_emission_at_row_month_is_exactly_m2_ghat():
    """Spec §2 (B-4): para s = m la emisión es exactamente el Ĝ de M2 en ese corte (motor y caché compartidos)."""
    s = Synth(4)
    rng = np.random.default_rng(0)
    ex = pd.DataFrame(rng.standard_normal((len(s.idx), 3)), index=s.idx, columns=list(MT.TRANS))
    s.X = s.X.join(ex.reindex(s.X.index))
    T = pd.Timestamp("1990-01-01")
    info = s.info(T)
    m2 = MS.StructuralG(rev="none")
    m2.fit_axis_continuous("G", None, None, None, None, info)
    g2 = m2.predict_axis_continuous("G", pd.DataFrame(index=[T]), info)[0][0]
    m3 = MT.TVTPG()
    eng = m3._ensure_version(info)
    assert m3._v is m2._v
    assert m3._emission(eng, [T], info)[0] == g2


def test_m3_variants_run_in_harness_with_criterion8():
    s = Synth(4)
    rng = np.random.default_rng(0)
    ex = pd.DataFrame(rng.standard_normal((len(s.idx), 3)), index=s.idx, columns=list(MT.TRANS))
    data = array_data(s, extra_X=ex)
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, **MT.REGISTRY}
    sf = {"m3_tvtp_g": {"coefs": ["G:gamma1", "G:gamma2", "G:gamma3", "G:gamma4"], "threshold": 0.01,
                        "min_frac": 0.5, "missing_counts_as_fail": True}}
    cfg = H.HarnessConfig(name="m3t", models=tuple(reg), modes=("synthetic",), test_start="1990-01",
                          test_end="1990-02", baseline="m0_calibrated_persistence", epochs=(),
                          min_train_recessions=0, min_train_g_changes=0, sign_fraction=sf)
    r = H.run(cfg, registry=reg, datas={"synthetic": data}, record=False)
    s8 = r["report"]["signos_coeficientes"]["synthetic/m3_tvtp_g"]
    assert all(v["n_cortes"] == 2 for v in s8["fraccion_umbral"].values())
    assert set(r["preds"]["model"]) == set(reg)
    c = [x["coef"] for x in r["diag"]["synthetic"] if x["model"] == "m3_ctp_g" and x.get("coef")][-1]
    assert all(c[f"G:gamma{j}"] == 0 for j in range(1, 5))
    c = [x["coef"] for x in r["diag"]["synthetic"] if x["model"] == "m3_tvtp_g_nocal" and x.get("coef")][-1]
    assert "G:cal_b" not in c
