from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""Reproduce the p=97 search (slow but small)."""
from ecdsa_edu.core.field import is_probable_prime
from ecdsa_edu.core.curve import Curve, enumerate_points
p=97
for a in range(p):
    for b in range(p):
        if (4*a**3+27*b*b)%p==0:continue
        c=Curve('candidate',p,a,b,(0,0),0,0)
        pts=enumerate_points(c)
        if not is_probable_prime(len(pts)):continue
        g=next(q for q in pts if q is not None)
        print('Found:',a,b,'G=',g,'n=',len(pts),'h=1')
        if (a,b,g,len(pts))==(0,5,(1,43),79):print('Matches the hard-coded toy-97 curve')
        if (a,b)==(0,5):raise SystemExit
