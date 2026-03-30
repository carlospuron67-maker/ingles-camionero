import joblib
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# =============================================================================
# 1. VALORES MAESTROS (LOS QUE TÚ PEGAS)
# =============================================================================
DNA_MASTER = {
    'RS_vs_SPY': 4.185,
    'Tightness': 1.690,
    'Media_Conv': 4.170,
    'Vol_DryUp': 0.585,
    'Dist_SMA50': 3.500,
    'Dist_Max': -7.500
}

UMBRAL_PARECIDO = 65.0  

LISTA_PREVIA = [
    'JNJ', 'COST', 'MRK', 'KO', 'LIN', 'VZ', 'CAT', 'AMGN', 'HON', 'PFE', 'DE', 'AMAT', 'GILD', 'T', 'LMT', 'LRCX', 'SBUX',
    'MO', 'TGT', 'CL', 'NOC', 'CSX', 'APD', 'FDX', 'MCK', 'ADM', 'AKAM', 'ATO', 'BALL', 'CBOE', 'CHD', 'CMS', 'CNP', 'DGX', 
    'DLR', 'DTE', 'DVA', 'EBAY', 'ENPH', 'ETN', 'ETR', 'FAST', 'FE', 'FFIV', 'GRMN', 'HAL', 'HII', 'HSY', 'HWM', 'IRM', 'JCI', 
    'KLAC', 'KMI', 'LHX', 'MSI', 'NI', 'PPL', 'REG', 'SRE', 'SYY', 'TDY', 'TMUS', 'WEC', 'WMB', 'XEL'
]

# =============================================================================
# 2. MOTOR LÓGICO (BASICO)
# =============================================================================

def get_hma(s, l):
    w = np.arange(1, l + 1)
    wma = lambda x: np.dot(x, w) / w.sum()
    h = s.rolling(l//2).apply(wma, raw=True) * 2 - s.rolling(l).apply(wma, raw=True)
    return h.rolling(int(np.sqrt(l))).apply(wma, raw=True)

def calcular_genes(df, spy_series):
    # Aseguramos que las fechas coincidan quitando zonas horarias
    df.index = pd.to_datetime(df.index).tz_localize(None)
    spy_series.index = pd.to_datetime(spy_series.index).tz_localize(None)
    
    common = df.index.intersection(spy_series.index)
    if len(common) < 60: return None
    
    c, v = df['Close'].loc[common], df['Volume'].loc[common]
    s_c = spy_series.loc[common]
    
    rs = ((c.iloc[-1]/c.iloc[-60]) - (s_c.iloc[-1]/s_c.iloc[-60])) * 100
    tight = (c.iloc[-10:].std() / c.iloc[-10:].mean()) * 100
    s10, s20, s50 = c.rolling(10).mean().iloc[-1], c.rolling(20).mean().iloc[-1], c.rolling(50).mean().iloc[-1]
    conv = (max(s10, s20, s50) / min(s10, s20, s50) - 1) * 100
    dry = v.iloc[-5:].mean() / v.iloc[-30:].mean()
    d50 = (c.iloc[-1] / s50 - 1) * 100
    dmax = (c.iloc[-1] / c.iloc[-60:].max() - 1) * 100
    
    return {'RS_vs_SPY': rs, 'Tightness': tight, 'Media_Conv': conv, 'Vol_DryUp': dry, 'Dist_SMA50': d50, 'Dist_Max': dmax}

def calcular_score(actual, maestro):
    escalas = {'RS_vs_SPY': 10.0, 'Tightness': 2.0, 'Media_Conv': 3.0, 'Vol_DryUp': 0.3, 'Dist_SMA50': 5.0, 'Dist_Max': 8.0}
    dist = sum(abs(actual[k] - maestro[k]) / escalas[k] for k in maestro.keys())
    return round(100 * np.exp(-dist / 12), 1)

def auditar(df):
    df.index = pd.to_datetime(df.index).tz_localize(None)
    ma = get_hma(df['Close'], 20)
    ang = (ma - ma.shift(2)).iloc[-1]
    return (ang > 0), "N/A" # Auditoría simplificada para estabilidad

# =============================================================================
# 3. PROCESO DE DATOS
# =============================================================================

try:
    data = joblib.load("data_maestra_descargadaspy.joblib")
    spy = data.get("SPY")
except:
    data, spy = {}, None

if data and spy is not None:
    final_list, report = [], []
    
    for t, df in data.items():
        if t == "SPY": continue
        try:
            genes = calcular_genes(df, spy['Close'])
            if genes is None: continue
            
            score = calcular_score(genes, DNA_MASTER)
            abierto, _ = auditar(df)
            
            se_queda = (score >= UMBRAL_PARECIDO) or (t in LISTA_PREVIA and abierto)
            
            if se_queda:
                final_list.append(t)
                report.append({"Ticker": t, "ADN": score, "RS": round(genes['RS_vs_SPY'], 1)})
        except: continue

    # Reporte
    if report:
        print(pd.DataFrame(report).sort_values(by="ADN", ascending=False).to_string(index=False))
    
    print(f"\n📋 LISTA FINAL: {', '.join([f'\'{t}\'' for t in final_list])}")
