from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""P1 performance check: run python tools/p1_benchmark.py from repository root."""
from time import perf_counter
from statistics import median
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.core.types import PrivateKey
from ecdsa_edu.core.keys import public_from_private
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.verify import verify

curve=get_curve('secp256k1');priv=PrivateKey(123456789,curve)
pub=public_from_private(priv);message=b'P1 benchmark'
times=[]
for _ in range(12):
    start=perf_counter();sig=sign(priv,message);ok=verify(pub,message,sig)
    assert ok
    times.append((perf_counter()-start)*1000)
print(f'Sign + verify median: {median(times):.2f} ms; target ~50 ms')
