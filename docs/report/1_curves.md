# 1. Elliptic curves and point arithmetic (P1)

## Finite fields

We use the short-Weierstrass equation \(y^2\equiv x^3+ax+b\pmod p\), where \(p\) is prime and \(4a^3+27b^2\not\equiv0\pmod p\). All coordinates and arithmetic are reduced modulo \(p\). The point at infinity \(O\) is the identity. For ECDSA we select a generator \(G\) of prime order \(n\): \(nG=O\).

## The group law

For different points \(P=(x_1,y_1)\), \(Q=(x_2,y_2)\), the slope is \(\lambda=(y_2-y_1)(x_2-x_1)^{-1}\pmod p\). For doubling, \(\lambda=(3x_1^2+a)(2y_1)^{-1}\pmod p\). Both use \(x_3=\lambda^2-x_1-x_2\pmod p\) and \(y_3=\lambda(x_1-x_3)-y_1\pmod p\) (doubling takes \(x_2=x_1\)). If points are negatives, their sum is \(O\). Doubling a point with \(y=0\) also produces \(O\).

## Double-and-add

To compute \(kG\), process the binary digits of \(k\) from left to right: double the accumulator, then add \(G\) when the current bit is 1. This takes \(O(\log k)\) group operations. The app uses affine coordinates for educational traces and an internal Jacobian path without traces for fast standard-curve computations.

## Why prime order matters

ECDSA calculates inverses modulo \(n\), including the nonce inverse \(k^{-1}\) and signature inverse \(s^{-1}\). A prime \(n\) makes every nonzero value invertible, preventing arithmetic failures caused by nontrivial factors. The generator subgroup has order \(n\), even if the full curve group has cofactor \(h\).

## Hand-checkable toy-17 example

Take \(p=17,a=2,b=2,G=(5,1),n=19\).

**2G:** \(\lambda=(3\cdot5^2+2)/(2\cdot1)=77/2\equiv9\cdot9=13\pmod{17}\), because \(77\equiv9\) and \(2^{-1}\equiv9\). Then \(x_3=13^2-10=159\equiv6\), \(y_3=13(5-6)-1=-14\equiv3\). Thus **\(2G=(6,3)\)**.

**3G = 2G + G:** with \((6,3)+(5,1)\), \(\lambda=(1-3)/(5-6)=(-2)/(-1)=2\pmod{17}\). Then \(x_3=2^2-6-5=-7\equiv10\), \(y_3=2(6-10)-3=-11\equiv6\). Thus **\(3G=(10,6)\)**.

The full table has 18 non-infinity multiples and \(19G=O\). Students can inspect each modular inversion, slope, and resulting point in the trace viewer.
