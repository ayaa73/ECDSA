"""Building the actual ECDSA key
key pair : (d,Q) s.t:
-d is the private key; a randomly chosen whole number between 1 and n-1
-Q is the public key: Q=d*G; G is of order n
Going from d to Q is one scalar multiplication, which is fast.
Getting d from Q and G should be hard to maintain secrecy of private key


Every function takes an optional `trace` list which has every step of calculations done  
--> trace= python list s.t every item is one step with its name, formula used, and values
--> our project is an educational app, we want to teach ECDSA so it's important to explain the steps and keep track of what was done 
--> can see how Q was reached for example using the trace
The only math functions used from P1 are scalar_mult and is_on_curve.
"""
import secrets # Python built-in module that gives secure random numbers; we will use to choose the private key 

from .curve import is_on_curve, scalar_mult # .curve is a file in our current folder ( core folder) 
#importing the function that returns true if the point satisfies the elliptic curve's equation (_is_on_curve)
# import the function that multiplies point P by number k
from .trace import add_step # this method takes as input trace, title, formula and values --> adds step to the trace list --> need it to write our own steps to the trace list
from .types import PrivateKey, PublicKey # our functions will return keys in these classes


def _show(number, curve): #deciding how the number should be shown on the screen
    """Turn a number into text for the trace: decimal on toy curves, hex on real ones."""
    if curve.p < 2**32: #p is the prime number we use for curve mod(p); every calculation wraps around at p 
        return str(number) # small curve,small p , decimal is easiest to read; every toy and custom curve is far below this value
    return hex(number) # real curve, ( ex secp256k1) have great number of digits--> too long to read in decimal so display in hex on screen


def generate_keypair(curve, trace=None): # creates a brand-new key pair from nothing on given curve curve
    #returns (private_key, public_key)
    n = curve.n # need n because d should be between 1 and n-1
    if n < 2: # if n is 1 then d would belong to [1;0] --> no possible key 
        raise ValueError("the base point order n must be at least 2")

    # Step 1: pick d at random from 1 to n-1.
    # secrets.randbelow(n - 1) gives number between 0 .. n-2 (all equally likely so attacker can't guess based on high likelihood); +1 makes it in range 1 .. n-1.
    # used secret instead of random because random can be predicted.
    d = secrets.randbelow(n - 1) + 1 # not n because nG = O --> would be no public key

    add_step(trace, "Choose the private key d", "d = random integer, 1 <= d <= n - 1",
             n=_show(n, curve), d=_show(d, curve)) #writes step 1 of the trace

    # Step 2: compute the matching public key Q = d * G.
    private_key = PrivateKey(d, curve)
    public_key = public_from_private(private_key, trace)
    return private_key, public_key


def public_from_private(priv, trace=None):
    #Compute the public key Q = d*G from given private key priv
   # Raises ValueError if d is not a whole number from 1 to n-1.
    
    curve = priv.curve
    d = priv.d

    # d must be an integer/whole number 
    if type(d) != int:
        raise ValueError("the private key d must be an integer")
# d must be from 1 to n-1.
    if d < 1 or d > curve.n - 1:
        raise ValueError("the private key d must satisfy 1 <= d <= n - 1 (n = " + _show(curve.n, curve) + ")")

    # we know that an elliptic curve has a fixed base point G , we're storing its coordinates here
    gx = curve.G[0] 
    gy = curve.G[1]
    add_step(trace, "Start from the base point G", "Q = d * G = G + G + ... + G (d times), using double-and-add",
             d=_show(d, curve), Gx=_show(gx, curve), Gy=_show(gy, curve))

    # calls the double-and-add function with k=d and P=G. It adds one trace step per bit of d.
    Q = scalar_mult(curve, d, curve.G, trace) # result is a point 

    # None means the point at infinity which never happens if n is correctly chosen 
    if Q is None:
        raise ValueError("d * G is the point at infinity - check the curve's order n")

    add_step(trace, "Public key Q = d * G", "Q = (Qx, Qy) is published; d stays secret",
             Qx=_show(Q[0], curve), Qy=_show(Q[1], curve))
    return PublicKey(Q, curve)


def validate_public_point(curve, Q):
    """Check that Q can  be used as a public key on the given curve

 --> does nothing if Q is fin but if it isn;t then it raises ValueError 
 -->every public key that comes from a file or another person goes through 4 steps so no fake point or weak point can be used
    """
    # Check 1:the point at infinity O is not a public key.
    if Q is None:
        raise ValueError("the point at infinity is not a valid public key")
    # Check 2: x and y must both be from 0 to p-1 ( everything si computed mod p)
    x = Q[0]
    y = Q[1]
    if x < 0 or x >= curve.p or y < 0 or y >= curve.p:
        raise ValueError("public key coordinates must be in the range [0, p - 1]")

    # Check 3: the point must be on the curve (y^2 = x^3 + ax + b mod p).
    if not is_on_curve(curve, Q):
        raise ValueError("this point is not on the curve")

    # Check 4: n * Q must be the point at infinity, which proves Q is in G's cycle.
    if scalar_mult(curve, curve.n, Q) is not None:
        raise ValueError("this point is not in the subgroup generated by G (n * Q != O)")
