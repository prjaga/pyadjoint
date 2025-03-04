import pytest
pytest.importorskip("firedrake")

from firedrake import *
from firedrake.adjoint import *

from numpy.random import default_rng
rng = default_rng()


def test_simple_solve():
    tape = Tape()
    set_working_tape(tape)

    mesh = IntervalMesh(10, 0, 1)
    V = FunctionSpace(mesh, "Lagrange", 1)

    f = Function(V)
    f.vector()[:] = 2

    u = TrialFunction(V)
    v = TestFunction(V)

    a = u*v*dx
    L = f*v*dx

    u_ = Function(V)

    solve(a == L, u_)

    L = u_*v*dx

    u_sol = Function(V)
    solve(a == L, u_sol)

    J = assemble(u_sol**4*dx)
    c = Control(f)
    Jhat = ReducedFunctional(J, c)

    h = Function(V)
    h.vector()[:] = rng.random(V.dim())

    tape.evaluate_adj()

    m = f.copy(deepcopy=True)
    dJdm = Jhat.derivative().vector().inner(h.vector())
    Hm = Jhat.hessian(h).vector().inner(h.vector())
    assert taylor_test(Jhat, m, h, dJdm=dJdm, Hm=Hm) > 2.9


def test_mixed_derivatives():
    tape = Tape()
    set_working_tape(tape)

    mesh = IntervalMesh(10, 0, 1)
    V = FunctionSpace(mesh, "Lagrange", 1)

    f = Function(V)
    f.vector()[:] = 2
    control_f = Control(f)

    g = Function(V)
    g.vector()[:] = 3
    control_g = Control(g)

    u = TrialFunction(V)
    v = TestFunction(V)

    a = f**2*u*v*dx
    L = g**2*v*dx

    u_ = Function(V)
    solve(a == L, u_)

    J = assemble(u_**2*dx)
    Jhat = ReducedFunctional(J, [control_f, control_g])

    # Direction to take a step for convergence test
    h = Function(V)
    h.vector()[:] = rng.random(V.dim())

    # Evaluate TLM
    control_f.tlm_value = h
    control_g.tlm_value = h
    tape.evaluate_tlm()

    # Evaluate Adjoint
    J.block_variable.adj_value = 1.0
    tape.evaluate_adj()

    # Evaluate Hessian
    J.block_variable.hessian_value = 0
    tape.evaluate_hessian()

    dJdm = J.block_variable.tlm_value
    Hm = control_f.hessian_value.vector().inner(h.vector()) + control_g.hessian_value.vector().inner(h.vector())

    m_1 = f.copy(deepcopy=True)
    m_2 = g.copy(deepcopy=True)

    assert taylor_test(Jhat, [f, g], [h, h], dJdm, Hm) > 2.9


def test_function():
    tape = Tape()
    set_working_tape(tape)

    mesh = IntervalMesh(10, 0, 1)
    V = FunctionSpace(mesh, "Lagrange", 2)

    c = Constant(4, domain=mesh)
    control_c = Control(c)
    f = Function(V)
    f.vector()[:] = 3
    control_f = Control(f)

    u = Function(V)
    v = TestFunction(V)
    bc = DirichletBC(V, Constant(1, domain=mesh), "on_boundary")

    F = inner(grad(u), grad(v)) * dx + u**2*v*dx - f ** 2 * v * dx - c**2*v*dx
    solve(F == 0, u, bc)

    J = assemble(c ** 2 * u ** 2 * dx)

    Jhat = ReducedFunctional(J, [control_c, control_f])
    dJdc, dJdf = compute_gradient(J, [control_c, control_f])

    # Step direction for derivatives and convergence test
    h_c = Constant(1.0, domain=mesh)
    h_f = Function(V)
    h_f.vector()[:] = 10*rng.random(V.dim())

    # Total derivative
    dJdc, dJdf = compute_gradient(J, [control_c, control_f])
    dJdm = dJdc.vector().inner(h_c) + dJdf.vector().inner(h_f)

    # Hessian
    Hcc, Hff = compute_hessian(J, [control_c, control_f], [h_c, h_f])
    Hm = Hff.vector().inner(h_f.vector()) + Hcc.vector().inner(h_c.vector())

    assert taylor_test(Jhat, [c, f], [h_c, h_f], dJdm=dJdm, Hm=Hm) > 2.9


def test_nonlinear():
    tape = Tape()
    set_working_tape(tape)

    mesh = UnitSquareMesh(10, 10)
    V = FunctionSpace(mesh, "Lagrange", 1)

    f = Function(V)
    f.vector()[:] = 5

    u = Function(V)
    v = TestFunction(V)
    bc = DirichletBC(V, Constant(1, domain=mesh), "on_boundary")

    F = inner(grad(u), grad(v)) * dx - u**2*v*dx - f * v * dx
    solve(F == 0, u, bc)

    J = assemble(u ** 4 * dx)
    Jhat = ReducedFunctional(J, Control(f))

    h = Function(V)
    h.vector()[:] = 10*rng.random(V.dim())

    J.block_variable.adj_value = 1.0
    f.block_variable.tlm_value = h

    tape.evaluate_adj()
    tape.evaluate_tlm()

    J.block_variable.hessian_value = 0
    tape.evaluate_hessian()

    g = f.copy(deepcopy=True)

    dJdm = J.block_variable.tlm_value
    Hm = f.block_variable.hessian_value.vector().inner(h.vector())
    assert taylor_test(Jhat, g, h, dJdm=dJdm, Hm=Hm) > 2.9


def test_dirichlet():
    tape = Tape()
    set_working_tape(tape)

    mesh = UnitSquareMesh(10, 10)
    V = FunctionSpace(mesh, "Lagrange", 1)

    f = Function(V)
    f.vector()[:] = 30

    u = Function(V)
    v = TestFunction(V)
    c = Function(V)
    c.vector()[:] = 1
    bc = DirichletBC(V, c, "on_boundary")

    F = inner(grad(u), grad(v)) * dx + u**4*v*dx - f**2 * v * dx
    solve(F == 0, u, bc, solver_parameters={"snes_rtol": 1e-10})

    J = assemble(u ** 4 * dx)
    Jhat = ReducedFunctional(J, Control(c))

    h = Function(V)
    h.vector()[:] = rng.random(V.dim())

    J.block_variable.adj_value = 1.0
    c.block_variable.tlm_value = h

    tape.evaluate_adj()
    tape.evaluate_tlm()

    J.block_variable.hessian_value = 0
    tape.evaluate_hessian()

    g = c.copy(deepcopy=True)

    dJdm = J.block_variable.tlm_value

    Hm = c.block_variable.hessian_value.vector().inner(h.vector())
    assert taylor_test(Jhat, g, h, dJdm=dJdm, Hm=Hm) > 2.9


def test_burgers():
    tape = Tape()
    set_working_tape(tape)
    n = 100
    mesh = UnitIntervalMesh(n)
    V = FunctionSpace(mesh, "CG", 2)

    def Dt(u, u_, timestep):
        return (u - u_)/timestep

    x, = SpatialCoordinate(mesh)
    pr = project(sin(2*pi*x), V, annotate=False)
    ic = Function(V)
    ic.vector()[:] = pr.vector()[:]

    u_ = Function(V)
    u = Function(V)
    v = TestFunction(V)

    nu = Constant(0.0001)

    timestep = Constant(1.0/n)

    F = (Dt(u, ic, timestep)*v
         + u*u.dx(0)*v + nu*u.dx(0)*v.dx(0))*dx
    bc = DirichletBC(V, 0.0, "on_boundary")

    t = 0.0
    solve(F == 0, u, bc)
    u_.assign(u)
    t += float(timestep)

    F = (Dt(u, u_, timestep)*v
         + u*u.dx(0)*v + nu*u.dx(0)*v.dx(0))*dx

    end = 0.2
    while (t <= end):
        solve(F == 0, u, bc)
        u_.assign(u)

        t += float(timestep)

    J = assemble(u_*u_*dx + ic*ic*dx)

    Jhat = ReducedFunctional(J, Control(ic))
    h = Function(V)
    h.vector()[:] = rng.random(V.dim())
    g = ic.copy(deepcopy=True)
    J.block_variable.adj_value = 1.0
    ic.block_variable.tlm_value = h
    tape.evaluate_adj()
    tape.evaluate_tlm()

    J.block_variable.hessian_value = 0
    tape.evaluate_hessian()

    dJdm = J.block_variable.tlm_value
    Hm = ic.block_variable.hessian_value.vector().inner(h.vector())
    assert taylor_test(Jhat, g, h, dJdm=dJdm, Hm=Hm) > 2.9
