"""Ratio histograms for the report: where wave 2 and wave 4 end, real data
against stationary-bootstrap surrogates (5 per symbol), whole period.

    python3 -m elliott.histograms stocks_daily
"""
import json, os, sys, zlib
import numpy as np

from . import behavior as B, data as D, waves

HERE = os.path.dirname(os.path.abspath(__file__))
BINS = np.round(np.arange(0.0, 1.0001, 0.02), 2)


def ratios(b, k=2.0):
    piv = waves.pivots(b["high"], b["low"], b["close"], k)
    x, kind, c = np.log(piv["p"]), piv["kind"], piv["c"]
    r2, r4 = [], []
    for j in range(3, len(x)):
        if not b["liquid"][c[j]]:
            continue
        W1, W2 = abs(x[j - 1] - x[j - 2]), abs(x[j] - x[j - 1])
        if W2 < W1:
            r2.append(W2 / W1)
        if j >= 5:
            d = 1 if kind[j] == -1 else -1
            if d * (x[j - 2] - x[j - 4]) > 0 and d * (x[j - 1] - x[j - 3]) > 0 and d * (x[j] - x[j - 3]) > 0:
                r4.append(abs(x[j] - x[j - 1]) / abs(x[j - 1] - x[j - 2]))
    return r2, r4


def main(dataset):
    bars = D.DATASETS[dataset]()
    real2, real4, s2, s4 = [], [], [], []
    for s, b in sorted(bars.items()):
        a, c = ratios(b)
        real2 += a; real4 += c
        for r in range(5):
            sb = B.surrogate(b, B.BLOCK[dataset], zlib.crc32(f"hist|{s}|{r}".encode()))
            a, c = ratios(sb)
            s2 += a; s4 += c
    out = {"bins": BINS.tolist()}
    for name, v in (("wave2_real", real2), ("wave2_null", s2), ("wave4_real", real4), ("wave4_null", s4)):
        h, _ = np.histogram(np.clip(v, 0, 0.9999), bins=BINS)
        out[name] = (h / max(1, len(v))).tolist()
        out[name + "_n"] = len(v)
    json.dump(out, open(f"{HERE}/results/histograms_{dataset}.json", "w"), indent=1)
    print({k: v for k, v in out.items() if k.endswith("_n")})


if __name__ == "__main__":
    main(sys.argv[1])
