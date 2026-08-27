# Changelog

Notable changes to csar. Terse by design — each entry points to the PR or
commit that carries the full detail.

## [Unreleased]

- **Breaking**: `method='alternating'` is gone — upstream retired that
  solver path. `method` is `'trust'` or `'auto'`.
- New `PrecisionFloor` outcome (`gap_tol` below what f64 can certify
  for the input); `Outcome` is now a four-way union, and both
  uncertified outcomes carry `gap_floor`.
- Builds against `csar_abi` (C ABI) v0.1.1, pinning csar 0.5.0; the
  vendored C shim is gone.

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
  Continues the prototype previously developed as
  [`skar_py`](https://github.com/ajfriend/skar_py), preserved as-is for its
  history and provenance.
