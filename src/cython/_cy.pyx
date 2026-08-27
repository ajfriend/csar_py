# cython: language_level=3
"""Cython binding for csar — internal; called from `csar.solve`.

Compiled by meson (driven by meson-python); links against the static
archive from csar_abi and declares the doors, code tables, and
defaults from its csar.h — no hand-copied prototypes or code values:
every integer the ABI speaks resolves by name through the C compiler.
Exposed as `csar._cy`.
"""

import numpy as np

from libc.stdint cimport int32_t, uint32_t


cdef extern from "csar.h":
    ctypedef struct csar_result:
        double q[9]
        double sigma[3]
        double gap
        double gap_floor
        double residual
        int32_t status
        int32_t method
        uint32_t n_iters

    int32_t csar_solve(const double *pts, uint32_t n, double gap_tol,
                       int32_t n_hull, double coplanarity_tol,
                       uint32_t max_outer, int32_t method, csar_result *out,
                       double *out_lambdas)

    enum:
        CSAR_OK
        CSAR_INSUFFICIENT_POINTS
        CSAR_INVALID_TOLERANCE
        CSAR_COPLANAR_INPUT
        CSAR_OUT_OF_MEMORY
        CSAR_INTERNAL
        CSAR_INVALID_METHOD
        CSAR_STATUS_CONVERGED
        CSAR_STATUS_INFEASIBLE
        CSAR_STATUS_DID_NOT_CONVERGE
        CSAR_STATUS_PRECISION_FLOOR
        CSAR_METHOD_TRUST
        CSAR_METHOD_AUTO
        CSAR_METHOD_NONE

    const double CSAR_DEFAULT_GAP_TOL
    const int32_t CSAR_DEFAULT_N_HULL
    const double CSAR_DEFAULT_COPLANARITY_TOL
    const uint32_t CSAR_DEFAULT_MAX_OUTER


# Upstream's SolveOptions defaults, by the header's names — `solve`'s
# keyword defaults in solver.py, so a retune upstream flows through.
DEFAULT_GAP_TOL = CSAR_DEFAULT_GAP_TOL
DEFAULT_N_HULL = CSAR_DEFAULT_N_HULL
DEFAULT_COPLANARITY_TOL = CSAR_DEFAULT_COPLANARITY_TOL
DEFAULT_MAX_OUTER = CSAR_DEFAULT_MAX_OUTER

# Code↔string tables keyed by the declared constants — a renumbering
# upstream re-keys these automatically (and an unknown code raises
# KeyError instead of mislabeling). Owned here, at the C boundary, so
# the raw integer codes never leak into the Python wrapper.
_STATUS = {
    CSAR_STATUS_CONVERGED: 'converged',
    CSAR_STATUS_INFEASIBLE: 'infeasible',
    CSAR_STATUS_DID_NOT_CONVERGE: 'did_not_converge',
    CSAR_STATUS_PRECISION_FLOOR: 'precision_floor',
}
_METHOD_NAME = {CSAR_METHOD_TRUST: 'trust'}
_METHOD_CODE = {'trust': CSAR_METHOD_TRUST, 'auto': CSAR_METHOD_AUTO}


def solve(double[:, ::1] pts not None, double gap_tol, int n_hull,
          double coplanarity_tol, unsigned int max_outer, str method):
    """Run csar_solve; returns a dict of `outcomes.build` keyword
    arguments — field names carried across the boundary, only the
    fields the outcome defines."""
    if pts.shape[1] != 3:
        raise ValueError('pts must be a 2-D array of shape (N, 3)')
    if method not in _METHOD_CODE:
        raise ValueError(
            f"csar: method must be 'trust' or 'auto'; got {method!r}"
        )

    cdef csar_result r
    # NULL lambdas: the certificate's dual multipliers are not surfaced
    # through the Python API yet; the nullable out-param is the door
    # for them when a consumer asks.
    cdef int32_t err = csar_solve(
        &pts[0, 0], <uint32_t>pts.shape[0], gap_tol, n_hull,
        coplanarity_tol, max_outer, _METHOD_CODE[method], &r, NULL,
    )

    if err == CSAR_INSUFFICIENT_POINTS:
        raise ValueError('csar: need at least 3 points to define a cone')
    if err == CSAR_INVALID_TOLERANCE:
        raise ValueError('csar: tolerances must be finite and positive')
    if err == CSAR_COPLANAR_INPUT:
        raise ValueError(
            'csar: input is (near-)coplanar — points lie ~on a great circle, '
            'so no meaningful enclosing cone exists. coplanarity_tol<=0 '
            'bypasses the near-coplanar check only; exactly rank-deficient '
            'input is always rejected.'
        )
    if err == CSAR_OUT_OF_MEMORY:
        raise MemoryError('csar: out of memory')
    if err == CSAR_INTERNAL:
        raise RuntimeError(
            'csar: internal solver error (a PSD/duality invariant was '
            'violated beyond float noise) — please report it'
        )
    if err == CSAR_INVALID_METHOD:
        raise ValueError("csar: method must be 'trust' or 'auto'")
    if err != CSAR_OK:
        raise RuntimeError(f'csar: unknown error code {err}')

    status = _STATUS[r.status]
    if r.status == CSAR_STATUS_INFEASIBLE:
        return {'status': status, 'residual': r.residual}

    # The arrays are contiguous in csar_result — fill ndarrays here
    # rather than round-tripping 12 floats through Python tuples.
    sigma = np.empty(3)
    Q = np.empty((3, 3))
    cdef double[::1] sv = sigma
    cdef double[:, ::1] qv = Q
    cdef int i, j
    for i in range(3):
        sv[i] = r.sigma[i]
        for j in range(3):
            qv[i, j] = r.q[i * 3 + j]  # row-major Q[r, c]

    out = {
        'status': status,
        'sigma': sigma,
        'Q': Q,
        'gap': r.gap,
        'outer_iters': r.n_iters,
        'method': None if r.method == CSAR_METHOD_NONE else _METHOD_NAME[r.method],
    }
    if r.status != CSAR_STATUS_CONVERGED:
        out['gap_floor'] = r.gap_floor
    return out
