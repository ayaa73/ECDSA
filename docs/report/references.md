# References

*Collected by Aya (P4). Starter list of 23 November 2026: every source already cited in section 4.4, the
Theory pages 08–10 and the History page. Each section writer: add your sources here in the same style, keeping
the numbering, and cite them in your text as [n].*

## Standards

[1] Standards for Efficient Cryptography Group, *SEC 1: Elliptic Curve Cryptography*, version 2.0, 2009.
    https://www.secg.org/sec1-v2.pdf

[2] Standards for Efficient Cryptography Group, *SEC 2: Recommended Elliptic Curve Domain Parameters*,
    version 1.0, 2000. https://secg.org/SEC2-Ver-1.0.pdf

[3] National Institute of Standards and Technology, *FIPS 186-5: Digital Signature Standard (DSS)*, 2023.
    https://csrc.nist.gov/pubs/fips/186-5/final

[4] T. Pornin, *RFC 6979: Deterministic Usage of the Digital Signature Algorithm (DSA) and Elliptic Curve
    Digital Signature Algorithm (ECDSA)*, IETF, August 2013. https://www.rfc-editor.org/rfc/rfc6979

[5] National Institute of Standards and Technology, *FIPS 204: Module-Lattice-Based Digital Signature
    Standard*, August 2024. https://csrc.nist.gov/pubs/fips/204/final

## Books and papers

[6] C. Paar and J. Pelzl, *Understanding Cryptography: A Textbook for Students and Practitioners*, Springer,
    2010. (Source of the toy-17 worked examples: $y^2 = x^3 + 2x + 2 \bmod 17$, $G = (5, 1)$.)

[7] W. Diffie and M. E. Hellman, "New Directions in Cryptography," *IEEE Transactions on Information Theory*,
    vol. 22, no. 6, pp. 644–654, 1976. https://ee.stanford.edu/~hellman/publications/24.pdf

[8] D. Johnson, A. Menezes and S. Vanstone, "The Elliptic Curve Digital Signature Algorithm (ECDSA),"
    *International Journal of Information Security*, vol. 1, pp. 36–63, 2001.
    https://doi.org/10.1007/s102070100002

[9] A. H. Koblitz, N. Koblitz and A. Menezes, "Elliptic Curve Cryptography: The Serpentine Course of a Paradigm
    Shift," CACR technical report 2008-19, University of Waterloo, 2008.
    https://cacr.uwaterloo.ca/techreports/2008/cacr2008-19.pdf

## Real-world incidents

[10] fail0verflow, "Console Hacking 2010: PS3 Epic Fail," talk at the 27th Chaos Communication Congress (27C3),
     December 2010. https://fahrplan.events.ccc.de/congress/2010/Fahrplan/attachments/1780_27c3_console_hacking_2010.pdf

[11] Bitcoin.org, "Android Security Vulnerability," alert of 11 August 2013.
     https://bitcoin.org/en/alert/2013-08-11-android

[12] N. Madden, "CVE-2022-21449: Psychic Signatures in Java," April 2022.
     https://neilmadden.blog/2022/04/19/psychic-signatures-in-java/

[13] Bitcoin Wiki, "Secp256k1." https://en.bitcoin.it/wiki/Secp256k1

## Software used in testing

[14] Python Cryptographic Authority, *cryptography* library (used only in tests, to cross-check our signatures).
     https://cryptography.io/

[15] pytest and pytest-qt (test runner and Qt GUI testing). https://docs.pytest.org/ ,
     https://pytest-qt.readthedocs.io/

## To be added by section writers

- Section 2 Research (Maria): the tools compared (CrypTool 2, CyberChef, ...), sources for where ECDSA is used.
- Section 6 Birthday attack (Mira): the MD5 rogue-CA paper, Flame, SHAttered, "SHA-1 is a Shambles".
- Section 7 Security notes (Mira): Minerva and TPM-FAIL (timing attacks), Bitcoin's low-s rule, cited in
  Theory page 09.
- Sections 4.1–4.3 (Maria, Serena, Mira): any further sources.
