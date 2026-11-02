"""csar — conic spherical aspect-ratio solver.

Given a point set on the unit sphere, find the tightest ellipsoidal cone
enclosing it and return its axis ratio. Thin Python bindings over the
`csar` Zig package.

Public API:
    solve(points, *, geo=..., ...) -> Outcome
    to_vec3(points, *, geo=...) -> np.ndarray
    plot_cone(result, geometry, ...) -> Axes        (needs matplotlib)
    project_to_cone(result, points, ...) -> (xy, semi)
    Outcome = Converged | Infeasible | DidNotConverge | PrecisionFloor
    versions() -> {'csar': ..., 'csar_abi': ..., 'csar_zig': ...}
    __version__
"""

from importlib.metadata import version as _dist_version

from . import _cy
from .convert import to_vec3
from .outcomes import Converged, DidNotConverge, Infeasible, Outcome, PrecisionFloor
from .plot import plot_cone, project_to_cone
from .solver import solve

# The package version has one source of truth, `[project] version` in
# pyproject.toml; read it back from the installed metadata.
__version__ = _dist_version('csar')


def versions() -> dict[str, str]:
    """Versions of the three layers behind a solve, for provenance:
    this package (`csar`), the C ABI it links (`csar_abi`), and the
    solver that ABI is built over (`csar_zig`)."""
    return {
        'csar': __version__,
        'csar_abi': _cy.ABI_VERSION,
        'csar_zig': _cy.UPSTREAM_VERSION,
    }


__all__ = [
    'solve',
    'versions',
    'to_vec3',
    'plot_cone',
    'project_to_cone',
    'Outcome',
    'Converged',
    'Infeasible',
    'DidNotConverge',
    'PrecisionFloor',
]
