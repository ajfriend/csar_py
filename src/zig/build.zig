//! Installs libcsar.{a,lib} + csar.h for the Cython extension to
//! compile and link against. Both come from csar_abi — the ABI repo
//! that owns the C door surface — pinned in build.zig.zon; this repo
//! no longer carries a shim of its own.

const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const abi = b.dependency("csar_abi", .{
        .target = target,
        .optimize = optimize,
    });
    // Named paths, not the artifact: csar_abi repacks the archive for
    // Apple's ld on macOS targets and exposes the consumable result
    // as `lib` (its dev.md "The archive and Apple's linker").
    const lib_name = if (target.result.os.tag == .windows) "csar.lib" else "libcsar.a";
    b.getInstallStep().dependOn(&b.addInstallLibFile(abi.namedLazyPath("lib"), lib_name).step);
    b.getInstallStep().dependOn(&b.addInstallHeaderFile(abi.namedLazyPath("header"), "csar.h").step);
}
