# Changelog

Notable changes to csar. Terse by design — each entry points to the PR or
commit that carries the full detail.

## [0.1.0]

- Initial release of `csar` (conic spherical aspect ratio): Python bindings
  for the [`skar_zig`](https://github.com/ajfriend/skar_zig) solver. Given a
  point set on the unit sphere, `csar.solve` returns the tightest enclosing
  ellipsoidal cone as a typed `Converged` / `Infeasible` / `DidNotConverge`
  outcome; `method=` selects the solver path (`'auto'` default, resolving to
  the trust-region method). Ships as a Cython extension with the upstream Zig
  solver statically linked — no separate shared library in the wheel.
  Continues the prototype previously developed under the `skar_py` name.
