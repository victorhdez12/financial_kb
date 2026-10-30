"""INT-7, decisión 4: la familia de Shiller entra en las permitidas con el mismo corte ≤ 2004 (y solo esas series)."""
from src.intl import data as D


def test_familia_shiller():
    for sid in ("shiller_cape", "shiller_real_price", "shiller_real_earnings", "shiller_real_dividend",
                "shiller_real_stock_tr_ret_m"):
        assert D.permitida(sid), sid
    for sid in ("shiller_tr_cape", "shiller_fwd10y_real_stock_ret", "shiller_excess_cape_yield", "shillerh_hpi_real_m",
                "shiller_cape_x"):
        assert not D.permitida(sid), sid


def test_shiller_corta_en_2004():
    con = D.connect()
    try:
        s = D.load_dev(con, "shiller_cape")
    finally:
        con.close()
    assert len(s) > 0 and s.index.max() <= D.DEV_END
