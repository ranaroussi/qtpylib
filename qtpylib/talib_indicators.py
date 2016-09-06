TALIB_MISSING = False

try:
    import talib
except ImportError:
    TALIB_MISSING = True
    raise ImportError("TA-Lib is not installed on this system!")
    pass

from pandas import Series, DataFrame


# ---------------------------
def _check_talib_presence():
    if TALIB_MISSING:
        raise ImportError("TA-Lib is not installed on this system!")

# ---------------------------
def _extract_series(data):
    values = None

    if isinstance(data, Series):
        values = data.values
    else:
        if "last" in data.columns:
            values = data['last'].values
        elif "close" in data.columns:
            values = data['close'].values

    if values is None:
        raise ValueError("data must be Pandas Series or DataFrame with a 'last' or 'close' column")

    return values

# ---------------------------
def _extract_ohlc(data):
    if isinstance(data, DataFrame):
        if "open" in data.columns and "high" in data.columns \
            and "low" in data.columns and "close" in data.columns \
            and "volume" in data.columns:
            return data[['open','high','low','close','volume']].T.values

    raise ValueError("data must be Pandas with OLHC columns")


# ---------------------------
# Overlap Studies
# ---------------------------
def BBANDS(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.BBANDS(prices, **kwargs)

def DEMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.DEMA(prices, **kwargs)

def EMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.EMA(prices, **kwargs)

def HT_TRENDLINE(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.HT_TRENDLINE(prices, **kwargs)

def KAMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.KAMA(prices, **kwargs)

def MA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MA(prices, **kwargs)

def MAMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MAMA(prices, **kwargs)

def MAVP(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MAVP(prices, **kwargs)

def MIDPOINT(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MIDPOINT(prices, **kwargs)

def MIDPRICE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.MIDPRICE(phigh, plow, **kwargs)

def SAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.SAR(phigh, plow, **kwargs)

def SAREXT(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.SAREXT(prices, **kwargs)

def SMA(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.SMA(phigh, plow, **kwargs)

def T3(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.T3(prices, **kwargs)

def TEMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.TEMA(prices, **kwargs)

def TRIMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.TRIMA(prices, **kwargs)

def WMA(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.WMA(prices, **kwargs)


# ---------------------------
# Momentum Indicators
# ---------------------------
def ADX(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.ADX(phigh, plow, pclose, **kwargs)

def ADXR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.ADXR(phigh, plow, pclose, **kwargs)

def APO(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.APO(prices, **kwargs)

def AROON(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.AROON(phigh, plow, **kwargs)

def AROONOSC(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.AROONOSC(phigh, plow, **kwargs)

def BOP(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.BOP(popen, phigh, plow, pclose, **kwargs)

def CCI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CCI(phigh, plow, pclose, **kwargs)

def CMO(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.CMO(prices, **kwargs)

def DX(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.DX(phigh, plow, pclose, **kwargs)

def MACD(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MACD(prices, **kwargs)

def MACDEXT(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MACDEXT(prices, **kwargs)

def MACDFIX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MACDFIX(prices, **kwargs)

def MFI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.MFI(popen, phigh, plow, pclose, pvolume, **kwargs)

def MINUS_DI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.MINUS_DI(phigh, plow, pclose, **kwargs)

def MINUS_DM(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.MINUS_DM(phigh, plow, **kwargs)

def MOM(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MOM(prices, **kwargs)

def PLUS_DI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.PLUS_DI(phigh, plow, pclose, **kwargs)

def PLUS_DM(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.PLUS_DM(phigh, plow, **kwargs)

def PPO(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.PPO(prices, **kwargs)

def ROC(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ROC(prices, **kwargs)

def ROCP(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ROCP(prices, **kwargs)

def ROCR(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ROCR(prices, **kwargs)

def ROCR100(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ROCR100(prices, **kwargs)

def RSI(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.RSI(prices, **kwargs)

def STOCH(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.STOCH(phigh, plow, pclose, **kwargs)

def STOCHF(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.STOCHF(phigh, plow, pclose, **kwargs)

def STOCHRSI(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.STOCHRSI(prices, **kwargs)

def TRIX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.TRIX(prices, **kwargs)

def ULTOSC(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.ULTOSC(phigh, plow, pclose, **kwargs)

def WILLR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.WILLR(phigh, plow, pclose, **kwargs)


# ---------------------------
# Volume Indicators
# ---------------------------
def AD(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.AD(popen, phigh, plow, pclose, pvolume, **kwargs)

def ADOSC(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.ADOSC(popen, phigh, plow, pclose, pvolume, **kwargs)

def OBV(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.OBV(pvolume, **kwargs)


# ---------------------------
# Cycle Indicators
# ---------------------------
def HT_DCPERIOD(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.HT_DCPERIOD(prices, **kwargs)

def HT_DCPHASE(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.HT_DCPHASE(prices, **kwargs)

def HT_PHASOR(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.HT_PHASOR(prices, **kwargs)

def HT_SINE(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.HT_SINE(prices, **kwargs)

def HT_TRENDMODE(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.HT_TRENDMODE(prices, **kwargs)


# ---------------------------
# Price Transform
# ---------------------------
def AVGPRICE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.AVGPRICE(popen, phigh, plow, pclose, **kwargs)

def MEDPRICE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.MEDPRICE(phigh, plow, **kwargs)

def TYPPRICE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.TYPPRICE(popen, phigh, plow, pclose, **kwargs)

def WCLPRICE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.WCLPRICE(phigh, plow, pclose, **kwargs)


# ---------------------------
# Volatility Indicators
# ---------------------------
def ATR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.ATR(phigh, plow, pclose, **kwargs)

def NATR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.NATR(phigh, plow, pclose, **kwargs)

def TRANGE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.TRANGE(phigh, plow, pclose, **kwargs)


# ---------------------------
# Parrern Recognition
# ---------------------------
def CDL2CROWS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL2CROWS(popen, phigh, plow, pclose, **kwargs)

def CDL3BLACKCROWS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL3BLACKCROWS(popen, phigh, plow, pclose, **kwargs)

def CDL3INSIDE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL3INSIDE(popen, phigh, plow, pclose, **kwargs)

def CDL3LINESTRIKE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL3LINESTRIKE(popen, phigh, plow, pclose, **kwargs)

def CDL3OUTSIDE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL3OUTSIDE(popen, phigh, plow, pclose, **kwargs)

def CDL3STARSINSOUTH(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL3STARSINSOUTH(popen, phigh, plow, pclose, **kwargs)

def CDL3WHITESOLDIERS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDL3WHITESOLDIERS(popen, phigh, plow, pclose, **kwargs)

def CDLABANDONEDBABY(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLABANDONEDBABY(popen, phigh, plow, pclose, **kwargs)

def CDLADVANCEBLOCK(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLADVANCEBLOCK(popen, phigh, plow, pclose, **kwargs)

def CDLBELTHOLD(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLBELTHOLD(popen, phigh, plow, pclose, **kwargs)

def CDLBREAKAWAY(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLBREAKAWAY(popen, phigh, plow, pclose, **kwargs)

def CDLCLOSINGMARUBOZU(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLCLOSINGMARUBOZU(popen, phigh, plow, pclose, **kwargs)

def CDLCONCEALBABYSWALL(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLCONCEALBABYSWALL(popen, phigh, plow, pclose, **kwargs)

def CDLCOUNTERATTACK(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLCOUNTERATTACK(popen, phigh, plow, pclose, **kwargs)

def CDLDARKCLOUDCOVER(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLDARKCLOUDCOVER(popen, phigh, plow, pclose, **kwargs)

def CDLDOJI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLDOJI(popen, phigh, plow, pclose, **kwargs)

def CDLDOJISTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLDOJISTAR(popen, phigh, plow, pclose, **kwargs)

def CDLDRAGONFLYDOJI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLDRAGONFLYDOJI(popen, phigh, plow, pclose, **kwargs)

def CDLENGULFING(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLENGULFING(popen, phigh, plow, pclose, **kwargs)

def CDLEVENINGDOJISTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLEVENINGDOJISTRAR(popen, phigh, plow, pclose, **kwargs)

def CDLEVENINGSTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLEVENINGSTAR(popen, phigh, plow, pclose, **kwargs)

def CDLGAPSIDESIDEWHITE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLGAPSIDESIDEWHITEITE(popen, phigh, plow, pclose, **kwargs)

def CDLGRAVESTONEDOJI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLGRAVESTONEDOJII(popen, phigh, plow, pclose, **kwargs)

def CDLHAMMER(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHAMMER(popen, phigh, plow, pclose, **kwargs)

def CDLHANGINGMAN(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHANGINGMAN(popen, phigh, plow, pclose, **kwargs)

def CDLHARAMI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHARAMI(popen, phigh, plow, pclose, **kwargs)

def CDLHARAMICROSS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHARAMICROSS(popen, phigh, plow, pclose, **kwargs)

def CDLHIGHWAVE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHIGHWAVE(popen, phigh, plow, pclose, **kwargs)

def CDLHIKKAKE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHIKKAKE(popen, phigh, plow, pclose, **kwargs)

def CDLHIKKAKEMOD(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHIKKAKEMOD(popen, phigh, plow, pclose, **kwargs)

def CDLHOMINGPIGEON(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLHOMINGPIGEON(popen, phigh, plow, pclose, **kwargs)

def CDLIDENTICAL3CROWS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLIDENTICAL3CROWS(popen, phigh, plow, pclose, **kwargs)

def CDLINNECK(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLINNECK(popen, phigh, plow, pclose, **kwargs)

def CDLINVERTEDHAMMER(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLINVERTEDHAMMER(popen, phigh, plow, pclose, **kwargs)

def CDLKICKING(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLKICKING(popen, phigh, plow, pclose, **kwargs)

def CDLKICKINGBYLENGTH(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLKICKINGBYLENGTH(popen, phigh, plow, pclose, **kwargs)

def CDLLADDERBOTTOM(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLLADDERBOTTOM(popen, phigh, plow, pclose, **kwargs)

def CDLLONGLEGGEDDOJI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLLONGLEGGEDDOJI(popen, phigh, plow, pclose, **kwargs)

def CDLLONGLINE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLLONGLINE(popen, phigh, plow, pclose, **kwargs)

def CDLMARUBOZU(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLMARUBOZU(popen, phigh, plow, pclose, **kwargs)

def CDLMATCHINGLOW(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLMATCHINGLOW(popen, phigh, plow, pclose, **kwargs)

def CDLMATHOLD(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLMATHOLD(popen, phigh, plow, pclose, **kwargs)

def CDLMORNINGDOJISTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLMORNINGDOJISTAR(popen, phigh, plow, pclose, **kwargs)

def CDLMORNINGSTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLMORNINGSTAR(popen, phigh, plow, pclose, **kwargs)

def CDLONNECK(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLONNECK(popen, phigh, plow, pclose, **kwargs)

def CDLPIERCING(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLPIERCING(popen, phigh, plow, pclose, **kwargs)

def CDLRICKSHAWMAN(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLRICKSHAWMAN(popen, phigh, plow, pclose, **kwargs)

def CDLRISEFALL3METHODS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLRISEFALL3METHODS(popen, phigh, plow, pclose, **kwargs)

def CDLSEPARATINGLINES(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLSEPARATINGLINES(popen, phigh, plow, pclose, **kwargs)

def CDLSHOOTINGSTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLSHOOTINGSTAR(popen, phigh, plow, pclose, **kwargs)

def CDLSHORTLINE(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLSHORTLINE(popen, phigh, plow, pclose, **kwargs)

def CDLSPINNINGTOP(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLSPINNINGTOP(popen, phigh, plow, pclose, **kwargs)

def CDLSTALLEDPATTERN(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLSTALLEDPATTERN(popen, phigh, plow, pclose, **kwargs)

def CDLSTICKSANDWICH(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLSTICKSANDWICH(popen, phigh, plow, pclose, **kwargs)

def CDLTAKURI(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLTAKURI(popen, phigh, plow, pclose, **kwargs)

def CDLTASUKIGAP(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLTASUKIGAP(popen, phigh, plow, pclose, **kwargs)

def CDLTHRUSTING(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLTHRUSTING(popen, phigh, plow, pclose, **kwargs)

def CDLTRISTAR(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLTRISTAR(popen, phigh, plow, pclose, **kwargs)

def CDLUNIQUE3RIVER(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLUNIQUE3RIVER(popen, phigh, plow, pclose, **kwargs)

def CDLUPSIDEGAP2CROWS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLUPSIDEGAP2CROWS(popen, phigh, plow, pclose, **kwargs)

def CDLXSIDEGAP3METHODS(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CDLXSIDEGAP3METHODS(popen, phigh, plow, pclose, **kwargs)


# ---------------------------
# Statistic Functions
# ---------------------------
def BETA(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.BETA(phigh, plow, **kwargs)

def CORREL(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.CORREL(phigh, plow, **kwargs)

def LINEARREG(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.LINEARREG(prices, **kwargs)

def LINEARREG_ANGLE(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.LINEARREG_ANGLE(prices, **kwargs)

def LINEARREG_INTERCEPT(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.LINEARREG_INTERCEPT(prices, **kwargs)

def LINEARREG_SLOPE(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.LINEARREG_SLOPE(prices, **kwargs)

def STDDEV(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.STDDEV(prices, **kwargs)

def TSF(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.TSF(prices, **kwargs)

def VAR(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.VAR(prices, **kwargs)


# ---------------------------
# Math Transform
# ---------------------------
def ACOS(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ACOS(prices, **kwargs)

def ASIN(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ASIN(prices, **kwargs)

def ATAN(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.ATAN(prices, **kwargs)

def CEIL(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.CEIL(prices, **kwargs)

def COS(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.COS(prices, **kwargs)

def COSH(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.COSH(prices, **kwargs)

def EXP(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.EXP(prices, **kwargs)

def FLOOR(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.FLOOR(prices, **kwargs)

def LN(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.LN(prices, **kwargs)

def LOG10(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.LOG10(prices, **kwargs)

def SIN(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.SIN(prices, **kwargs)

def SINH(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.SINH(prices, **kwargs)

def SQRT(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.SQRT(prices, **kwargs)

def TAN(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.TAN(prices, **kwargs)

def TANH(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.TANH(prices, **kwargs)


# ---------------------------
# Math Operators
# ---------------------------
def ADD(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.ADD(phigh, plow, **kwargs)

def DIV(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.DIV(phigh, plow, **kwargs)

def MAX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MAX(prices, **kwargs)

def MAXINDEX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MAXINDEX(prices, **kwargs)

def MIN(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MIN(prices, **kwargs)

def MININDEX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MININDEX(prices, **kwargs)

def MINMAX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MINMAX(prices, **kwargs)

def MINMAXINDEX(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.MINMAXINDEX(prices, **kwargs)

def MULT(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.MULT(phigh, plow, **kwargs)

def SUB(data, **kwargs):
    _check_talib_presence()
    popen, phigh, plow, pclose, pvolume = _extract_ohlc(data)
    return talib.SUB(phigh, plow, **kwargs)

def SUM(data, **kwargs):
    _check_talib_presence()
    prices = _extract_series(data)
    return talib.SUM(prices, **kwargs)
