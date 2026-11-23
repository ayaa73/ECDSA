"""Additional P1 edge and trace coverage."""
import pytest
from ecdsa_edu.core.field import inv_mod, sqrt_mod, is_probable_prime
from ecdsa_edu.core.curve import (Curve, point_add, point_double, point_neg, scalar_mult,
    make_custom_curve, enumerate_points)
from ecdsa_edu.core.curves_registry import get_curve

def test_invalid_modulus():
    with pytest.raises(ValueError): inv_mod(2, 1)

def test_noninvertible_trace():
    trace=[]
    with pytest.raises(ValueError): inv_mod(6, 9, trace)
    assert any(s.title == 'No inverse' for s in trace)

def test_field_edge_cases():
    assert sqrt_mod(0, 17)==0
    assert sqrt_mod(1, 2)==1
    assert sqrt_mod(4, 7) in (2,5)
    assert sqrt_mod(3, 7) is None
    with pytest.raises(ValueError): sqrt_mod(1, 9)
    assert not is_probable_prime(1)

def test_point_edges():
    c=get_curve('toy-17');g=c.G
    assert point_add(c,None,g)==g
    assert point_add(c,g,None)==g
    assert point_add(c,g,point_neg(c,g)) is None
    assert point_double(c,None) is None
    assert scalar_mult(c,0,g) is None
    assert scalar_mult(c,-1,g)==point_neg(c,g)
    with pytest.raises(ValueError):point_add(c,(0,0),g)
    with pytest.raises(ValueError):scalar_mult(c,1,g,trace_detail='bad')
    trace=[];assert scalar_mult(c,3,g,trace=trace,trace_detail='full')==(10,6)
    assert any(s.title=='Scalar bit' for s in trace)

def test_custom_validation():
    for args in [(9,2,2,(5,1)),(5003,2,2,(5,1)),(17,0,0,(0,0)),(17,2,2,(0,0))]:
        with pytest.raises(ValueError):make_custom_curve(*args)
    with pytest.raises(ValueError):enumerate_points(get_curve('secp256k1'))
