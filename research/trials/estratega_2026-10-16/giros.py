# Descomposición de los baselines <= 2004 (run 20261016-092402_baselines_v1_27cae755) en meses de giro / estables.
# La etiqueta dura se reconstruye SOLO a partir de las rachas publicadas en report.json (<= 2004). Sin variables.
import json, pandas as pd, numpy as np
D='/Users/victorhdez12/financial_archive/models/runs/20261016-092402_baselines_v1_27cae755/'
r=json.load(open(D+'report.json'))['report']
sc=pd.read_parquet(D+'scores.parquet')
eps=r['por_episodio']['vintage/climatology']['episodios']
lab={}
for e in eps:
    if e['tipo']!='racha_regimen': continue
    q,start=e['id'].split(' '); s=pd.Timestamp(start+'-01')
    for i in range(e['n']): lab[s+pd.DateOffset(months=i)]=q
lab=pd.Series(lab).sort_index()
rec=[(pd.Timestamp(e['id'].split(' ')[1]+'-01'),e['n']) for e in eps if e['tipo']=='recesion_nber']
G={'expansion':1,'late_cycle':1,'stagflation':0,'low_growth_disinfl':0}
I={'expansion':0,'late_cycle':1,'stagflation':1,'low_growth_disinfl':0}
# lag-5 change indicator; prior to sample start use first available (1956-10..) -> undefined for first 5 months
l5=lab.shift(5)
chg=(lab!=l5)&l5.notna()
# months since last change
since=[];k=99;prev=None
for m,q in lab.items():
    k=0 if (prev is not None and q!=prev) else k+1; since.append(k); prev=q
since=pd.Series(since,index=lab.index)
cat=pd.Series(np.where(since<=5,'giro_0-5m',np.where(since<=11,'6-11m','estable_12m+')),index=lab.index)
gch=(lab.map(G)!=l5.map(G))&l5.notna(); ich=(lab.map(I)!=l5.map(I))&l5.notna()
axis=pd.Series(np.select([gch&ich,gch,ich],['ambos','solo_G','solo_I'],'sin_cambio'),index=lab.index)
era=pd.Series(np.where(lab.index.year<1980,'1956-79','1980-2004'),index=lab.index)
inrec=pd.Series(False,index=lab.index)
for s,n in rec:
    for i in range(n): inrec[s+pd.DateOffset(months=i)]=True  # ya incluye ±6
out=[]
for mode in ['vintage','latest_truncated']:
  for model in ['persistence_pit','climatology']:
    x=sc[(sc['mode']==mode)&(sc['model']==model)].set_index('month')
    x=x.join(pd.DataFrame({'chg5':chg,'cat':cat,'axis':axis,'era':era,'rec6':inrec}))
    for col in ['chg5','cat','axis','era','rec6']:
        g=x.groupby(col).agg(n=('logloss','size'),ll=('logloss','mean'),acierto=('hit','mean'),
                             ll_total=('logloss','sum'))
        g['cuota_ll']=g['ll_total']/x['logloss'].sum()
        for k,row in g.iterrows(): out.append((mode,model,col,str(k),int(row.n),round(row.ll,3),round(row.acierto,3),round(row.cuota_ll,3)))
o=pd.DataFrame(out,columns=['modo','modelo','corte','grupo','n','logloss','acierto','cuota_logloss'])
pd.set_option('display.width',200)
print(o.to_string())
print('rachas', (lab!=lab.shift()).sum(), 'meses', len(lab))
rl=lab.groupby((lab!=lab.shift()).cumsum()).size()
print('longitud rachas: <=2:',(rl<=2).sum(),' 3-5:',((rl>=3)&(rl<=5)).sum(),' >=6:',(rl>=6).sum(), ' meses en rachas >=6:', rl[rl>=6].sum())
