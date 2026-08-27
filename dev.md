# Development notes

Internal-facing notes on architecture, build mechanics, and
contributor workflows for `csar`.

## Architecture

A thin Cython binding over `csar_abi` — the ABI repo that owns the C
door surface over the upstream `csar` solver. The Python side accepts
points as
`(lat, lng)` (degrees by default) or unit `(x, y, z)` vectors,
normalizes them to a contiguous `(N, 3)` float64 buffer with NumPy,
and hands that buffer to the Cython extension via a typed memoryview
(`double[:, ::1]`) — no copy. `[3]f64` on the Zig side is exactly that
row layout, so the shim reinterprets the pointer with no per-element
conversion.

The C ABI itself lives in neither this repo nor the solver — the
split is three layers, each intentional:

- **`csar_zig` (upstream)**: pure Zig solver library. Exports a
  `Module` for other Zig code; no C ABI, no shared library.
- **`csar_abi`**: the one C door surface (`csar_solve`, the
  `csar_result` struct, the code tables, `csar.h`), built as a static
  archive for native hosts and a wasm module for browsers, with a
  CI gate keeping the declarations in lockstep. Pins `csar_zig` by
  tag.
- **`csar` (this repo)**: depends on `csar_abi` via
  `build.zig.zon`, installs its archive + `csar.h`, and links the
  archive directly into the Cython extension `_cy.<EXT>`. `_cy.pyx`
  declares everything — prototypes, code tables, defaults — from
  `csar.h`, so no integer the ABI speaks is hand-copied here.

libcsar is a **static** archive (not a shared library) so it gets
pulled into `_cy.so` / `_cy.pyd` at link time. That sidesteps both the
Windows MSVC CRT mismatch and the macOS dylib `__dso_handle`
regression that shipping a Zig *dynamic* library triggers — the same
rationale as the sibling `sparea_py` bindings.

### What the ABI exposes (minimal surface)

`csar.solve` (Zig) returns a tagged `Outcome` union (`converged` /
`infeasible` / `did_not_converge` / `precision_floor`), not a single
scalar. `csar_solve` writes a caller-allocated `csar_result` struct —
`status` plus the per-variant payload (`sigma`, `q`, `gap`,
`gap_floor`, `residual`, `n_iters`, `method`); which fields a status
defines is documented on the struct in `csar.h`, and fields a variant
doesn't define hold NaN / sentinel values. The cone axis
(`Q[:, 0]`) and aspect ratio (`sigma[2]/sigma[1]`) are derivable, so
they're **not** in the ABI — they're computed Python-side.

The Python wrapper turns the `status` discriminator into one of four
classes — `Converged`, `Infeasible`, `DidNotConverge`,
`PrecisionFloor` (union alias `Outcome`) — each holding only its
variant's fields. This mirrors the
Zig tagged union: there is no shared object with `None`-valued fields,
so reading e.g. `aspect_ratio` on an `Infeasible` is an `AttributeError`
(and a static type error under `isinstance`/`match` narrowing) rather
than a silent `None`. `aspect_ratio` is a property on `Converged` only —
the uncertified outcomes withhold it, just as the Zig `Converged`
variant alone has the `aspectRatio()` method.

The active-set **certificate** (the dual multipliers) is not surfaced
through the Python API yet: `csar_solve` takes a nullable
`out_lambdas` and this binding passes NULL — the door is there when a
consumer asks.

`csar_solve`'s return value is the errors-vs-outcome split from
upstream: `CSAR_OK` = "ran, see `status`"; other codes = "could not
run" (insufficient points, invalid tolerance, coplanar input, OOM, or
an internal PSD/duality violation). `_cy.pyx` maps each to the
matching Python exception, by the header's names.

## Layout

```
.
├── pyproject.toml          — meson-python config, package metadata
├── meson.build             — drives Zig static-archive build + Cython compile
├── justfile                — reinstall / test / wheel / examples / clean
├── src/
│   ├── cython/
│   │   └── _cy.pyx         — Cython binding, exposes _cy.solve
│   ├── csar/
│   │   ├── __init__.py     — gathers the public API (solve, to_vec3, plot_cone, Outcome…)
│   │   ├── convert.py      — input → (N, 3) unit vectors: to_vec3, geo-interface
│   │   ├── outcomes.py     — the four Outcome classes + build()
│   │   ├── plot.py         — plot_cone (optional matplotlib helper)
│   │   └── solver.py       — solve(): convert → _cy.solve → build
│   └── zig/
│       ├── build.zig       — installs libcsar.{a,lib} + csar.h from csar_abi
│       └── build.zig.zon   — pins the csar_abi dependency
├── scripts/                — examples (own dep groups; not part of the wheel)
│   ├── states/             — US-state aspect ratios (`just states`)
│   └── countries/          — country aspect ratios (`just countries`)
└── tests/
    └── test_bindings.py
```

The wheel ships a single `_cy.<EXT>` (the Cython extension with
libcsar statically linked in); no separate dylib.

## Building and testing locally

```sh
just test       # reinstall (rebuild) + uv run pytest, ~4s
just reinstall  # rebuild only
just wheel      # uv build  (see the dependency-pin caveat below)
```

`uv sync` invokes meson-python, which runs Zig (via `python -m ziglang
build`, since `ziglang` is in `[build-system].requires`), then
cythonizes `src/cython/_cy.pyx` and links the result against the Zig
static archive. No host-level Zig or Cython install is needed — both come
from PyPI as build deps.

### The test loop (~4s, non-editable)

csar is a **non-editable** install (`UV_NO_EDITABLE=1`), so the wheel is
exercised as it ships. uv does *not* rebuild a non-editable install when
the source changes, so `just test` runs `reinstall`
(`uv sync --reinstall-package csar`) to pick up edits, then pytest. About
**4 seconds**, and reliably so. Two settings keep it there — both about the
*rebuild machinery*, since the Zig compile itself is never the bottleneck
(a cold ReleaseFast build is ~4s, a warm one ~0.07s):

- **`reinstall` passes `--no-build-isolation-package csar --group build`.**
  The `build` group holds the backend (`meson-python`, `ninja`, `cython`,
  `ziglang`); `--reinstall-package` then reuses those from the venv instead
  of staging a fresh isolated build env — which would re-install ziglang
  (~50 MB) and friends every time, ~5s of overhead (~9s total vs ~4s). These
  are **local flags only**: CI and `uv build` (sdist/wheels) build `csar`
  with normal isolation, so the package never carries a `no-build-isolation`
  setting (an earlier `[tool.uv]` version of this broke `uv build` in CI).
- **no `uv cache clean`** in `reinstall`. `--reinstall-package` already
  forces a rebuild, so the clean buys nothing — and it serializes on uv's
  global cache lock, which once stalled for the full 300s lock timeout when
  another uv process held it. That 300s hang, not the build, was the only
  genuinely slow run.

`ci-test` uses `uv run --no-sync` so the already-built env (from `reinstall`
locally, or `uv sync` in CI) isn't rebuilt a second time. CI's `test`
workflow sets `UV_NO_EDITABLE=1` so its `uv sync` also installs non-editable.

An *editable* install would cut this to ~0.5s via meson-python's
rebuild-on-import, but that hook shells out to `ninja` and is fragile under
uv's build isolation (stale `ninja` path → `FileNotFoundError`); not worth
the machinery for a ~4s gap.

## The csar_abi dependency: release pin vs. local path

`src/zig/build.zig.zon` pins `csar_abi` (which in turn pins the
`csar` solver by tag — bumping the solver happens there, not here).
The repo ships a **URL+hash pin to a released tag** — the form
wheels/CI need, since they build from an isolated sdist copy that
can't see a sibling checkout:

```zig
.csar_abi = .{
    .url = "https://github.com/ajfriend/csar_abi/archive/refs/tags/v0.1.0.tar.gz",
    .hash = "csar_abi-0.1.0-...",
},
```

To **co-develop both repos**, temporarily swap to a local path — no
network, no GitHub needed. `just test` / `uv sync` resolve it in-place;
only sdist/wheel builds (`uv build`, `just wheel`, CI) need the URL form,
since they build from a temp dir where `../../../csar_abi` doesn't exist:

```zig
.csar_abi = .{ .path = "../../../csar_abi" },   // relative to src/zig/
```

To **bump to a newer csar_abi** (or restore the URL pin after local dev):

```sh
cd src/zig && zig fetch --save=csar_abi \
  https://github.com/ajfriend/csar_abi/archive/refs/tags/vX.Y.Z.tar.gz
```

That rewrites `dependencies.csar_abi` to `.url` + `.hash`; re-run `just test`.
Caveat: if the existing entry is a `.path`, `--save` overwrites the path
*value* with the URL and adds no hash — first clear it to
`.dependencies = .{}`, then fetch.

## Continuous integration

- `.github/workflows/test.yml` — runs `just ci-test` across
  {Linux, macOS, Windows} × {3.11–3.14}.
- `.github/workflows/wheels.yml` — builds the sdist + the full
  cibuildwheel matrix, and on a published GitHub release publishes to
  PyPI via OIDC trusted publishing.

Both build from an isolated sdist using the URL+hash pin above, so they
need `csar_abi` pushed and tagged on GitHub (it is). If you switch to a
local `.path` for co-development, the in-place `test` workflow's
`uv sync` still works, but the `wheels` sdist build won't until you
restore the URL pin.

## Cutting a release

csar publishes to **PyPI** (https://pypi.org/project/csar/) automatically on a
published GitHub release, via the `to-pypi` job in `wheels.yml` — OIDC trusted
publishing (no API tokens), gated by the repo's `pypi` GitHub environment
(a required-reviewer approval step). The first PyPI release was `0.1.1`.

> **The package version has ONE source of truth: `[project] version` in
> `pyproject.toml`.** Bump only that. `meson.build`'s `project()` deliberately
> carries no `version:` (meson-python reads pyproject), so there is no second
> place to keep in sync. The git tag `vX.Y.Z` must match that version.

Steps:

1. **Pin a released `csar_abi`** (see above) if bumping the ABI or solver, and commit.
2. **Bump `[project] version`** in `pyproject.toml`, add a `changelog.md`
   entry, commit + push to `main`. Wait for `test` and `wheels` to go green.
3. **Create a GitHub release**: tag `vX.Y.Z` (matching the pyproject version),
   target `main`, write notes (link the `skar_py` provenance for the record).
4. **Approve the publish.** The release event triggers `wheels`; its `to-pypi`
   job builds the sdist + full wheel matrix, then pauses on the `pypi`
   environment — **approve the deployment** to let it upload via OIDC.
5. **Verify** in a fresh env: `uv pip install csar==X.Y.Z` + a quick solve.

PyPI versions and git tags are immutable — if an upload fails mid-publish, bump
to `X.Y.Z+1` rather than reusing the number. (This is why `0.1.0`, which was
GitHub-only and predates the publish job, is not on PyPI: PyPI starts at
`0.1.1`.)

### What ships in the artifacts

- **Wheel:** the `csar/` package + the compiled `_cy` extension (with the
  `csar_abi` static archive linked in) + metadata. Nothing else.
- **Sdist:** build inputs (`pyproject.toml`, `meson.build`, `src/`), `tests/`,
  and `readme`/`LICENSE`/`changelog`. Repo/dev-only files (`.github/`,
  `justfile`, `dev.md`, `scripts/`, `.gitignore`) are kept out of the sdist via
  `.gitattributes` `export-ignore` — meson-python builds the sdist from
  `git archive HEAD`, which honors those rules.
