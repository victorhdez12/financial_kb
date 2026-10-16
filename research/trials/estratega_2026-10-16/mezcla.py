# Cálculo indicativo <= 2004 (Estratega macro, 2026-10-16): cuánto de la ventaja sobre la persistencia PIT es solo
# calibración. Mezcla FIJA persistencia/climatología (predicciones walk-forward ya publicadas del run
# 20261016-092402_baselines_v1_27cae755) puntuada contra la etiqueta oficial <= 2004 leída por la caja fuerte (development).
# También log-loss binaria por eje (G, I) de la persistencia. Sin variables; nada >= 2005.
import sys; sys.path.insert(0,'/Users/victorhdez12/Proyectos/financial_kb')
import pandas as pd, numpy as np
from src.models.vault import LabelVault
D='/Users/victorhdez12/financial_archive/models/runs/20261016-092402_baselines_v1_27cae755/'
P=pd.read_parquet(D+'predictions.parquet')
lab=LabelVault('development').load(end='2004-12-01')
lab=lab.set_index('date') if 'date' in lab.columns else lab
lab.index=pd.to_datetime(lab.index)
assert lab.index.max()<pd.Timestamp('2005-01-01')
Q=['p_expansion','p_late_cycle','p_stagflation','p_low_growth_disinfl']
def clipn(a):
    a=np.clip(a,1e-4,None); return a/a.sum(1,keepdims=True)
def bll(p,t):
    p=np.clip(p,1e-4,1-1e-4); return -(t*np.log(p)+(1-t)*np.log(1-p))
for mode in ['vintage','latest_truncated']:
    pe=P[(P['mode']==mode)&(P.model=='persistence_pit')].set_index('month')[Q]
    cl=P[(P['mode']==mode)&(P.model=='climatology')].set_index('month')[Q]
    idx=pe.index.intersection(cl.index).intersection(lab.index)
    T=lab.loc[idx,Q].to_numpy()
    res={}
    for w in [1.0,0.9,0.8,0.7,0.6,0.5]:
        M=clipn(w*pe.loc[idx].to_numpy()+(1-w)*cl.loc[idx].to_numpy())
        res[w]=round(float((-(T*np.log(M)).sum(1)).mean()),4)
    pp=clipn(pe.loc[idx].to_numpy())
    pg=pp[:,0]+pp[:,1]; pi=pp[:,1]+pp[:,2]
    llg=bll(pg,lab.loc[idx,'p_g_high'].to_numpy()).mean(); lli=bll(pi,lab.loc[idx,'p_i_high'].to_numpy()).mean()
    print(mode,'n',len(idx),'mezcla w->logloss',res,'| persistencia eje G',round(llg,4),'eje I',round(lli,4))
# --- añadido: por meses de giro (label_hard(t) != label_hard(t-5)) y suelo irreducible (entropía de T)
h=lab['label_hard']; chg=(h!=h.shift(5))
for mode in ['vintage']:
    pe=P[(P['mode']==mode)&(P.model=='persistence_pit')].set_index('month')[Q]
    cl=P[(P['mode']==mode)&(P.model=='climatology')].set_index('month')[Q]
    idx=pe.index.intersection(cl.index).intersection(lab.index)
    T=lab.loc[idx,Q].to_numpy(); c=chg.loc[idx].to_numpy()
    ent=-(T*np.log(np.clip(T,1e-12,None))).sum(1)
    print('suelo (entropía media de la etiqueta blanda)',round(ent.mean(),4),'giro',round(ent[c].mean(),4),'estable',round(ent[~c].mean(),4))
    for w in [1.0,0.8]:
        M=clipn(w*pe.loc[idx].to_numpy()+(1-w)*cl.loc[idx].to_numpy()); ll=-(T*np.log(M)).sum(1)
        print('w',w,'giro n',c.sum(),round(ll[c].mean(),3),'estable n',(~c).sum(),round(ll[~c].mean(),3))
