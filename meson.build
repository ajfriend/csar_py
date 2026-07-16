# No `version:` here on purpose — the package version has a single source of
# truth: `[project] version` in pyproject.toml. meson-python reads it from
# there; a version in this project() call would be an unused, drift-prone copy.
project('csar', 'c', 'cython',
  meson_version: '>=1.4.0',
)

py = import('python').find_installation(pure: false)

# Per-platform name of Zig's static-archive output.
zig_out_name = host_machine.system() == 'windows' ? 'csar.lib' : 'libcsar.a'

# Pin macOS deployment target so the .a matches the wheel's claimed
# minimum (cibuildwheel sets MACOSX_DEPLOYMENT_TARGET; locally default
# to 11.0, matching CPython's own minimum).
zig_args = ['-m', 'ziglang', 'build', '-Doptimize=ReleaseFast',
  '--build-file', meson.current_source_dir() / 'src' / 'zig' / 'build.zig']
if host_machine.system() == 'darwin'
  arch = host_machine.cpu_family() == 'aarch64' ? 'aarch64' : 'x86_64'
  macos_min = run_command(py, '-c',
    'import os; print(os.environ.get("MACOSX_DEPLOYMENT_TARGET", "11.0"))',
    check: true).stdout().strip()
  zig_args += '-Dtarget=' + arch + '-macos.' + macos_min
endif

# Run `zig build` and ask Zig to install its lib directly into the
# meson build dir (so meson's custom_target output basename matches).
libcsar = custom_target('libcsar',
  output: zig_out_name,
  command: [py, zig_args,
    '--prefix', meson.current_build_dir(),
    '--prefix-lib-dir', '.'],
  console: true,
)

py.extension_module('_cy',
  'src/cython/_cy.pyx',
  link_with: libcsar,
  install: true,
  subdir: 'csar',
)

py.install_sources(
  'src/csar/__init__.py',
  'src/csar/convert.py',
  'src/csar/outcomes.py',
  'src/csar/plot.py',
  'src/csar/solver.py',
  subdir: 'csar',
)
