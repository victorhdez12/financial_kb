# Diagnóstico Estratega macro sobre M1 (2026-10-16). Solo <= 2004, desarrollo. Corrida larga 20261016-141648 (vintage).
# A) estudio de eventos alrededor de los giros oficiales de G (p_g_high cruza 0,5; ≥ 6 m a cada lado);
# B) Sahm frente a growth_rt y etiqueta oficial (descriptivo condicional) ≤ 2004.
import sys; sys.path.insert(0,'/Users/victorhdez12/Proyectos/financial_kb')
import pandas as pd, numpy as np
from src.models.vault import LabelVault
from src.features import pit as P
D='/Users/victorhdez12/financial_archive/models/runs/20261016-141648_m1_logit_axis_v1_long_0e55b60b/'
pr=pd.read_parquet(D+'predictions.parquet'); pr=pr[pr['mode']=='vintage']
lab=LabelVault('development').load(end='2004-12-01'); lab=lab.set_index('date') if 'date' in lab.columns else lab
lab.index=pd.to_datetime(lab.index); assert lab.index.max()<pd.Timestamp('2005-01-01')
pg={m:(g.set_index('month')['p_expansion']+g.set_index('month')['p_late_cycle']) for m,g in pr.groupby('model')}
M0,M1=pg['m0_calibrated_persistence'],pg['m1_logit_axis_hl']
idx=M0.index.intersection(M1.index)
t=lab['p_g_high']; s=(t>0.5).astype(int)
run=(s!=s.shift()).cumsum(); rl=s.groupby(run).transform('size')
turns=[m for m in s.index[1:] if s[m]!=s.shift()[m] and rl[m]>=6 and rl[s.index[s.index.get_loc(m)-1]]>=6 and m>=idx.min()+pd.DateOffset(months=6) and m<=idx.max()-pd.DateOffset(months=8)]
def bll(p,y):
    p=np.clip(p,1e-4,1-1e-4); return -(y*np.log(p)+(1-y)*np.log(1-p))
rows=[]
for m in turns:
    d=s[m]  # 1 = sube (salida), 0 = baja (entrada)
    for k in range(-6,9):
        mm=m+pd.DateOffset(months=k)
        if mm not in idx: continue
        rows.append(dict(turn=m,dir='sube' if d==1 else 'baja',k=k,lab=t[mm],m0=M0[mm],m1=M1[mm],
                         ll0=bll(M0[mm],t[mm]),ll1=bll(M1[mm],t[mm])))
E=pd.DataFrame(rows)
print('giros de G (≥6 m a cada lado) en 1975-06..2004:',len(turns),[f"{m:%Y-%m}{'↑' if s[m] else '↓'}" for m in turns])
pd.set_option('display.width',200)
for d,g in E.groupby('dir'):
    a=g.groupby('k')[['lab','m0','m1','ll0','ll1']].mean().round(3); a['mejora_M1']=(a.ll0-a.ll1).round(3)
    print('\nDirección',d,'n giros',g.turn.nunique()); print(a.T.to_string())
# B) Sahm
X=pd.read_parquet(P.out_dir()/'pit_us_v0.3_vintage.parquet',filters=[('decision_date','<',pd.Timestamp('2005-01-01').to_datetime64())],
                  columns=['decision_date','unrate_sahm','growth_rt'])
X['month']=X.decision_date.dt.to_period('M').dt.to_timestamp(); X=X.set_index('month')
Z=X.join(lab[['p_g_high','usrec']],how='inner').loc['1964-01':'2004-12'].dropna()
print('\ncorr(sahm, growth_rt) 1964-2004:',round(Z.unrate_sahm.corr(Z.growth_rt),3))
Z['sahm_on']=Z.unrate_sahm>=0.5; Z['gr_pos']=Z.growth_rt>0
print(Z.groupby(['sahm_on','gr_pos']).p_g_high.agg(['size','mean']).round(3).to_string())
# residual de sahm sobre growth_rt y relación con p_g_high
b=np.polyfit(Z.growth_rt,Z.unrate_sahm,1); Z['sahm_res']=Z.unrate_sahm-np.polyval(b,Z.growth_rt)
Z['res_q']=pd.qcut(Z.sahm_res,5,labels=False)
print(Z.groupby('res_q').agg(n=('p_g_high','size'),pg=('p_g_high','mean'),gr=('growth_rt','mean'),sahm=('unrate_sahm','mean')).round(3).to_string())
# Sahm tras el mínimo NBER: meses 0..12 tras el fin de recesión
u=Z.usrec.astype(int); ends=u.index[(u==1)&(u.shift(-1)==0)]
R=[]
for e in ends:
    for k in range(0,13,2):
        mm=e+pd.DateOffset(months=k)
        if mm in Z.index: R.append(dict(fin=e,k=k,sahm=Z.unrate_sahm[mm],gr=Z.growth_rt[mm],pg=Z.p_g_high[mm]))
R=pd.DataFrame(R); print('\nTras el fin de cada recesión NBER (1964-2004):'); print(R.groupby('k')[['sahm','gr','pg']].mean().round(2).T.to_string())
