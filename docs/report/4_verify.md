# 4. Verification, the nonce-reuse attack, and testing

*Author: P4. Code: `core/verify.py`, `core/attacks.py`, `gui/tabs/verify_tab.py`, `gui/tabs/attack_tab.py`.*

Notation follows the rest of the report: curve $E: y^2 = x^3 + ax + b \pmod p$, generator $G$ of prime
order $n$, private key $d \in [1, n-1]$, public key $Q = dG$, message hash $e$ (the hash output as an
integer, truncated to the bit length of $n$), nonce $k$, signature $(r, s)$, point at infinity $\mathcal{O}$.

## 4.1 The verification algorithm

Our `verify(pub, msg, sig)` implements SEC 1 v2, section 4.1.4. Given $Q$, a message $m$ and $(r, s)$:

1. **Range check.** Reject unless $1 \le r \le n-1$ and $1 \le s \le n-1$.
2. **Public-key check.** Reject unless $Q \ne \mathcal{O}$ and $Q$ satisfies the curve equation.
   (For a cofactor $h > 1$ we also require $nQ = \mathcal{O}$; all our curves have $h = 1$.)
3. **Hash.** $e = H(m)$, truncated exactly as in signing (section 3).
4. $w = s^{-1} \bmod n$.
5. $u_1 = e\,w \bmod n$, $\quad u_2 = r\,w \bmod n$.
6. $X = u_1 G + u_2 Q$. Reject if $X = \mathcal{O}$.
7. Accept if and only if $x_X \bmod n = r$.

Two design decisions:

- **`verify` never raises.** Every failure, including malformed inputs and internal errors, returns
  `False`. A verifier that throws on hostile input is a denial-of-service risk and is easy to misuse
  (a caller that catches the exception might treat the signature as "not rejected").
- **Every rejection is explained.** The last trace step is titled `INVALID: <reason>`, for example
  `r out of range`, `public key is not on the curve` or `x1 mod n != r`. The Verify tab shows this
  reason under the red INVALID banner, so a student sees *which* check failed, not just that one did.

`verify_file` is identical except that $e$ comes from the chunked `hash_file` (section 3), so large
files are never loaded into memory at once.

## 4.2 Why verification works

The signer computed $R = kG$, $r = x_R \bmod n$ and $s = k^{-1}(e + rd) \bmod n$. Multiplying the last
equation by $k\,s^{-1} = k\,w$ gives

$$k \equiv w\,(e + rd) \pmod n.$$

The verifier does not know $d$ or $k$, but $Q = dG$ lets it multiply by $d$ "inside a point":

$$u_1 G + u_2 Q = (ew)\,G + (rw)\,(dG) = w\,(e + rd)\,G = kG = R.$$

Hence $x_X \bmod n = x_R \bmod n = r$ for every correctly made signature. Conversely, if $m$, $r$, $s$ or
$Q$ is changed, the scalar $w(e + rd)$ changes, $X$ lands on an unrelated point, and the comparison
fails except with probability about $2/n$, which is negligible for a 256-bit $n$. Recovering $d$ from
$Q$ instead would require solving the ECDLP.

### Worked example (toy-17)

$E: y^2 = x^3 + 2x + 2 \pmod{17}$, $G = (5, 1)$, $n = 19$ (the example from Paar and Pelzl).
Alice has $d = 7$, so $Q = 7G = (0, 6)$. She signs a message with $e = 26$ using $k = 10$:
$R = 10G = (7, 11)$, $r = 7$, $s = 10^{-1}(26 + 7 \cdot 7) = 2 \cdot 75 \equiv 17 \pmod{19}$.

| Step | Computation | Result |
|---|---|---|
| Range | $1 \le 7,\ 17 \le 18$ | pass |
| Key | $(0, 6)$: $36 \equiv 0 + 0 + 2 \pmod{17}$ | on curve |
| $w$ | $17^{-1} \bmod 19$ | $9$ |
| $u_1$ | $26 \cdot 9 \bmod 19$ | $6$ |
| $u_2$ | $7 \cdot 9 \bmod 19$ | $6$ |
| $X$ | $6G + 6Q = (16, 13) + (3, 1)$ | $(7, 11)$ |
| Compare | $7 \bmod 19 \overset{?}{=} 7$ | **valid** |

If the message is altered so that $e = 25$, then $u_1 = 25 \cdot 9 \equiv 16$ and
$X = 16G + 6Q = 16G + 42G = 58G = G = (5, 1)$. Since $5 \ne 7$, the signature is **invalid**.

These are exactly the values the app's trace shows (they are checked by
`test_textbook_example_valid` in `tests/test_verify.py`).

## 4.3 The nonce-reuse attack

If the same $k$ signs two messages with hashes $e_1 \ne e_2$, both signatures share $R = kG$ and so the
same $r$. The two signing equations are

$$s_1 k \equiv e_1 + rd, \qquad s_2 k \equiv e_2 + rd \pmod n.$$

Subtracting eliminates $d$, and then the first equation gives $d$:

$$k \equiv \frac{e_1 - e_2}{s_1 - s_2} \pmod n, \qquad d \equiv \frac{s_1 k - e_1}{r} \pmod n.$$

`recover_from_nonce_reuse` implements this and traces each step. It then **checks its answer** by
computing $Q' = dG$ and verifying both signatures under $Q'$, so it never returns a wrong key silently.
It raises `ValueError` when the input cannot be a nonce-reuse pair ($r_1 \ne r_2$, identical signatures,
or $e_1 \equiv e_2$).

**Low-s signers.** Many implementations replace $s$ by $n - s$ when $s > n/2$ (section 4.5). That is the
same as signing with $-k$, and if only one of the two signatures was flipped, the formula above returns
a wrong $d$. Our function also tries $s_2 \to n - s_2$ and keeps the candidate whose key verifies both
signatures. This also covers the edge case where the flipped $s_2$ equals $s_1$ exactly.

### Worked example (toy-17)

Same key $d = 7$ and the same nonce $k = 10$ (so $r = 7$) used for two messages with $e_1 = 26$ and
$e_2 = 13$:

| | $e$ | $s = k^{-1}(e + rd) \bmod 19$ |
|---|---|---|
| Message 1 | 26 | $2 \cdot (26 + 49) = 150 \equiv 17$ |
| Message 2 | 13 | $2 \cdot (13 + 49) = 124 \equiv 10$ |

The attacker sees $r_1 = r_2 = 7$ and computes, with $7^{-1} \equiv 11 \pmod{19}$:

- $k = (26 - 13) \cdot (17 - 10)^{-1} = 13 \cdot 11 = 143 \equiv 10$
- $d = (17 \cdot 10 - 26) \cdot 7^{-1} = 144 \cdot 11 \equiv 11 \cdot 11 = 121 \equiv 7$
- Check: $7G = (0, 6) = Q$. The private key is recovered.

In 2010 this exact mistake exposed Sony's PlayStation 3 signing key, because the same $k$ was used for
every signature. The Attack Demo tab replays the attack live on toy-17 or secp256k1.

## 4.4 Security notes

This application is **educational and must not be used to protect real keys**:

- **Not constant-time.** Python integers and our double-and-add scalar multiplication take time that
  depends on the scalar. Timing leaks of even a few nonce bits enable lattice attacks (e.g. Minerva and
  TPM-FAIL, 2019).
- **Nonce generation.** Signing uses RFC 6979 deterministic nonces by default (section 3), which removes
  the dependence on a random number generator and rules out accidental reuse. The Attack Demo forces a
  repeated $k$ on purpose.
- **Malleability.** If $(r, s)$ is valid then so is $(r, n - s)$. `normalize_low_s` (section 3) produces
  the canonical low-s form. Our verifier accepts both forms, as SEC 1 requires.
- **Input validation.** The range and public-key checks in 4.1 are mandatory. Java 15–18 omitted the
  range check and accepted $r = s = 0$ for any message (CVE-2022-21449).
- **Keys on disk.** Private keys are saved as plain JSON (section 2), without encryption.

## 4.5 Testing summary

All tests run with `pytest`. Correctness is cross-checked against independent libraries, which are used
only inside tests.

| Area | What is tested | Status |
|---|---|---|
| Verification (toy-17) | Textbook example gives $w = 9$, $u_1 = u_2 = 6$, $X = (7, 11)$, valid | Written; passes with stand-in modules, pending merge of P1/P3 code |
| Rejection reasons | Tampered message, $r$ or $s$; $r$ or $s$ equal to 0 or $\ge n$; wrong key; key not on curve; garbage input never raises | Written; passes with stand-ins, pending merge |
| Library interop (theirs → ours) | Signatures from `cryptography` on secp256k1 and P-256 verify with our code | Written; passes with stand-ins, pending merge |
| Library interop (ours → theirs) | Our signatures verify with `cryptography` (DER via `sig_to_der`) | To do (needs P3's `sign` and `sig_encoding`) |
| RFC 6979 test vectors | Deterministic $k$ and signatures match the RFC | P3 (section 3) |
| Nonce-reuse attack | Recovers the true $d$ on toy-17, toy-97, secp256k1; low-s flip; flipped $s_2 = s_1$ edge case; errors for $r_1 \ne r_2$ and identical signatures | Written; passes with stand-ins, pending merge |
| Learn wizard | Missing teammate pages show "coming soon"; Back/Next; curve toggle; quiz scoring | Model tests pass; Qt tests need PySide6 |
| Fuzzing | 1000 round trips on toy-97, 50 on P-256; random bytes into every parser raise only `ValueError` | To do (week 4) |

*Final pass/fail counts will be filled in once all branches are merged.*
