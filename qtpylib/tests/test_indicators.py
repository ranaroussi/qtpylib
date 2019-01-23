from nose.tools import eq_
import pandas as pd
import numpy as np
from qtpylib import indicators as qtind

def test_indicator_stoch_slow():
    """Test the stochastic indicator logic"""

    data = {'open': range(15, 150, 15),
            'high': range(20, 200, 20),
            'low': range(10, 100, 10),
            'close': range(10, 100, 10),
        }

    df = pd.DataFrame(data=data)
    my_stoch = qtind.stoch(df, window=5, d=3, k=3, fast=False)

    last_stoch_slow_k = int(my_stoch['slow_k'].tail(1)*1000)
    last_stoch_slow_d = int(my_stoch['slow_d'].tail(1)*1000)
    eq_(last_stoch_slow_k, 33488)
    eq_(last_stoch_slow_d, 36774)

def test_indicator_stoch_fast():
    """Test the stochastic indicator logic"""

    data = {'open': range(15, 150, 15),
            'high': range(20, 200, 20),
            'low': range(10, 100, 10),
            'close': range(10, 100, 10),
        }

    df = pd.DataFrame(data=data)
    my_stoch = qtind.stoch(df, window=5, d=3, k=3, fast=True)

    last_stoch_fast_k = int(my_stoch['fast_k'].tail(1)*1000)
    last_stoch_fast_d = int(my_stoch['fast_d'].tail(1)*1000)
    eq_(last_stoch_fast_k, 30769)
    eq_(last_stoch_fast_d, 33488)
