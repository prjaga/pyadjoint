import pytest
pytest.importorskip("firedrake")

from numpy.testing import assert_allclose
from firedrake import *
from firedrake.adjoint import *


def test_optimisation_constant_control():
    """This tests a list of controls in a minimisation (through scipy L-BFGS-B)"""
    mesh = UnitSquareMesh(1, 1)

    n = 3
    x = [Constant(0., domain=mesh) for i in range(n)]
    c = [Control(xi) for xi in x]

    # Rosenbrock function https://en.wikipedia.org/wiki/Rosenbrock_function
    # with minimum at x = (1, 1, 1, ...)
    f = sum(100*(x[i+1] - x[i]**2)**2 + (1 - x[i])**2 for i in range(n-1))

    J = assemble(f * dx(domain=mesh))
    rf = ReducedFunctional(J, c)
    result = minimize(rf)
    assert_allclose([float(xi) for xi in result], 1., rtol=1e-4)


def _simple_helmholz_model(V, source):
    u = Function(V)
    v = TestFunction(V)
    F = inner(grad(v), grad(u))*dx + 100.0*v*u*dx - v*source*dx
    solve(F==0, u)
    return u


def test_simple_inversion():
    """Test inversion of source term in helmholze eqn."""
    mesh = UnitIntervalMesh(10)
    V = FunctionSpace(mesh, "CG", 1)
    ref = Function(V)
    source_ref = Function(V)
    x = SpatialCoordinate(mesh)
    source_ref.interpolate(cos(pi*x**2))

    # compute reference solution
    with stop_annotating():
        u_ref = _simple_helmholz_model(V, source_ref)

    # now rerun annotated model with zero source
    source = Function(V)
    c = Control(source)
    u = _simple_helmholz_model(V, source)

    J = assemble(1e6 * (u - u_ref)**2*dx)
    rf = ReducedFunctional(J, c)

    x = minimize(rf)
    assert_allclose(x.dat.data, source_ref.dat.data, rtol=1e-2)
