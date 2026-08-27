"""Result types returned by `solve`.

`solve` returns one of the four classes below — never a shared object
with None-valued fields. Each carries only the data meaningful for its
outcome, so reading e.g. ``.aspect_ratio`` on an `Infeasible` is an
immediate AttributeError (and a static type error under isinstance/match
narrowing) rather than a silent None. This mirrors the Zig `Outcome`
tagged union, where ``aspectRatio()``/``Q`` live only on the `Converged`
variant.

Every outcome also carries a ``.status`` string (the snake_case class name)
and a ``.converged`` bool (``True`` only on `Converged`) for quick checks —
e.g. ``if r.converged:`` — without a full ``isinstance``/``match``. Note that
`Infeasible` is a *valid* result (no cone exists), not a solver failure, which
is why the flag is named ``converged`` rather than ``success``.

``eq=False`` on the array-bearing classes: the dataclass-generated
``__eq__`` (a field-wise compare) raises on NumPy's ambiguous array
truth value, so these compare by identity instead.
"""

from dataclasses import dataclass
from typing import ClassVar, Literal

import numpy as np


@dataclass(frozen=True, eq=False, slots=True)
class Converged:
    """A certified enclosing cone was found.

    Attributes:
        sigma: ``(3,)`` float64 eigenvalues of ``A``, paired with the
            columns of ``Q``. ``sigma[0]`` is the structural axial
            eigenvalue (``1/sqrt(3)``); ``sigma[1] <= sigma[2]`` are the
            tangent-plane semi-axes.
        Q: ``(3, 3)`` float64 eigenbasis of ``A``. **Column** ``i`` is
            the unit eigenvector paired with ``sigma[i]``: ``Q[:, 0]`` is
            the cone axis; ``Q[:, 1]`` and ``Q[:, 2]`` are the
            cross-section ellipse's semi-axis directions. Right-handed
            (``det(Q) = +1``). Reconstruct ``A`` as
            ``Q @ np.diag(sigma) @ Q.T``.
        gap: certified duality gap (``<=`` the ``gap_tol`` passed to
            ``solve``).
        outer_iters: total solver iterations for the path that produced
            this outcome.
        method: which solver path produced this outcome — currently
            always ``'trust'``. Under ``method='auto'`` this is the
            concrete path the alias resolved to.
    """

    sigma: np.ndarray
    Q: np.ndarray
    gap: float
    outer_iters: int
    method: Literal['trust']
    status: ClassVar[Literal['converged']] = 'converged'
    converged: ClassVar[bool] = True

    @property
    def aspect_ratio(self) -> float:
        """Cross-section aspect ratio ``sigma[2] / sigma[1]`` (``>= 1``)."""
        return float(self.sigma[2] / self.sigma[1])


@dataclass(frozen=True, slots=True)
class Infeasible:
    """No hemisphere contains all the input points, so no enclosing cone
    exists.

    Attributes:
        residual: witness magnitude ``‖∑ λᵢ xᵢ‖``, near zero by
            construction.
    """

    residual: float
    status: ClassVar[Literal['infeasible']] = 'infeasible'
    converged: ClassVar[bool] = False


@dataclass(frozen=True, eq=False, slots=True)
class DidNotConverge:
    """The solver stopped with the gap still above this input's
    ``gap_floor``: the iteration budget (``max_outer``) ran out, or the
    search went stationary short of the floor. The last iterate is
    exposed for diagnostics / warm-start, but it is **not** a certified
    result — there is deliberately no ``aspect_ratio`` here. Compute
    ``sigma[2] / sigma[1]`` from ``sigma`` yourself if you want the
    uncertified estimate. Remedy: raise ``max_outer``.

    Attributes:
        sigma: ``(3,)`` last-iterate eigenvalues (see `Converged`),
            uncertified.
        Q: ``(3, 3)`` last-iterate eigenbasis (see `Converged`),
            uncertified.
        gap: gap at the last certified iterate — *not* certified to be
            below ``gap_tol``; inspect alongside ``outer_iters``. The
            sentinel value ``1e30`` means no certificate could ever be
            constructed (``Q``/``sigma`` carry no information then).
        gap_floor: the smallest gap certifiable at f64 for this input's
            geometry.
        outer_iters: total iterations run by the path that produced this
            outcome.
        method: which solver path produced this outcome (see
            `Converged.method`).
    """

    sigma: np.ndarray
    Q: np.ndarray
    gap: float
    gap_floor: float
    outer_iters: int
    method: Literal['trust']
    status: ClassVar[Literal['did_not_converge']] = 'did_not_converge'
    converged: ClassVar[bool] = False


@dataclass(frozen=True, eq=False, slots=True)
class PrecisionFloor:
    """``gap_tol`` is below what f64 can certify for this input
    (``gap_floor``), and the iterate is at that floor. The cone is as
    accurate as the input allows — only the certificate is missing.
    Raising ``max_outer`` changes nothing; loosen ``gap_tol`` (e.g. to
    just above ``gap_floor``) to get a `Converged` instead. Same payload
    as `DidNotConverge`, and like it, deliberately no ``aspect_ratio``.

    Attributes:
        sigma: ``(3,)`` floor-iterate eigenvalues, uncertified but
            input-precision-accurate.
        Q: ``(3, 3)`` floor-iterate eigenbasis.
        gap: gap at the last certified iterate.
        gap_floor: the smallest gap certifiable at f64 for this input's
            geometry — the tolerance to loosen toward.
        outer_iters: total iterations run.
        method: which solver path produced this outcome.
    """

    sigma: np.ndarray
    Q: np.ndarray
    gap: float
    gap_floor: float
    outer_iters: int
    method: Literal['trust']
    status: ClassVar[Literal['precision_floor']] = 'precision_floor'
    converged: ClassVar[bool] = False


# Union of the four outcomes — use as the return annotation and for
# `isinstance(x, Outcome)` (a native `|` union is a types.UnionType,
# which supports isinstance checks on py>=3.10).
Outcome = Converged | Infeasible | DidNotConverge | PrecisionFloor


_STATUS_CLS = {
    'converged': Converged,
    'infeasible': Infeasible,
    'did_not_converge': DidNotConverge,
    'precision_floor': PrecisionFloor,
}


def build(status, **fields) -> Outcome:
    """Assemble the typed `Outcome` from `_cy.solve`'s payload dict.

    `_cy.solve` returns exactly the fields the outcome defines, by
    name — a field mismatch fails loudly here as a TypeError rather
    than transposing values positionally.
    """
    return _STATUS_CLS[status](**fields)
