"""Calibrate the behavior tests on random walks: excess over surrogates should be about 0.

    cd strategy-lab && python3 -m elliott.calibration.behavior [symbols]
"""
import sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np

from elliott import behavior as B
from elliott.calibration.walks import path_walk
from elliott.tests.test_setups import bars_from


def job(s):
    b = bars_from(*path_walk(2700, 5000 + s))
    return B._symbol((f"R{s}", b, b["t"][0], b["t"][-1], 20, 2.0))


def main(n_sym=120):
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(job, range(n_sym)))
    for t in B.TESTS:
        R = np.array([r[1][t] for r in res], float)
        S = np.array([r[2][t] for r in res], float)
        o = B.symbol_bootstrap(R, S, draws=2000)
        print(f"{t}: n {o['events']:6d} real {o['real_share']:.4f} null {o['null_share']:.4f} "
              f"excess {o['excess']:+.4f} [{o['lo']:+.4f},{o['hi']:+.4f}]")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
