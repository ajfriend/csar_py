# Changelog

Notable changes to csar. Terse by design — each entry points to the PR or
commit that carries the full detail.

## [0.1.1]

- First PyPI release. Enable OIDC trusted-publishing upload in the `wheels`
  workflow (`to-pypi` job, runs on a published GitHub release). No functional
  change from 0.1.0 — the 0.1.0 tag predates the publish job, so this is the
  first version pushed to PyPI.

## [0.1.0]

- Initial release of `csar` (conic spherical aspect ratio): Python bindings
  for the [`csar_zig`](https://github.com/ajfriend/csar_zig) solver. Given a
  point set on the unit sphere, `csar.solve` returns the tightest enclosing
  ellipsoidal cone as a typed `Converged` / `Infeasible` / `DidNotConverge`
  outcome; `method=` selects the solver path (`'auto'` default, resolving to
  the trust-region method). Ships as a Cython extension with the upstream Zig
  solver statically linked — no separate shared library in the wheel.
  Continues the prototype previously developed under the `skar_py` name.
