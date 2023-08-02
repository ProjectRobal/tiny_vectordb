
# https://ninja-build.org/manual.html
from ninja import ninja_syntax
import pybind11
import os, sysconfig, subprocess, platform


__this_dir = os.path.dirname(os.path.abspath(__file__))
__this_dir = os.path.abspath(os.path.realpath(__this_dir))
SRC_DIR = os.path.join(__this_dir, "src")
HEADER_DIR = os.path.join(__this_dir, "include")
BUILD_DIR = os.path.join(__this_dir, "build")
BIN_DIR = os.path.join(BUILD_DIR, "lib")

eigen_src_path = os.path.join(__this_dir, "External", "eigen")
ninja_build_file = os.path.join(BUILD_DIR, "build.ninja")

for _d in [BUILD_DIR, BIN_DIR]:
    if not os.path.exists(_d):
        os.mkdir(_d)

def _writeNinja(feat_dim: int):
    module_name = _get_module_name(feat_dim)

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    py_includes = sysconfig.get_config_var('INCLUDEPY')

    with open(ninja_build_file, "w") as build_file:
        writer = ninja_syntax.Writer(build_file)

        writer.comment("This file is generated by build.py")
        cxx_flags = [
            "-std=c++17",
            "-Wall",
            "-fPIC",
            f"-I{eigen_src_path}",
            f"-I{py_includes}",
            f"-I{pybind11.get_include()}",
            f"-I{HEADER_DIR}",
            f"-DFEAT_DIM={feat_dim}",
            f"-DMODULE_NAME={module_name}",

            ## Optimization flags
            "-O2",
            "-funroll-loops",
            "-march=native",
            "-mtune=native",
        ]

        link_flags = [
            "-shared",
            "-lstdc++",
            "-static",      # must be static! as we will compile multiple modules with different feat_dim
        ]
        if platform.system() == "Darwin":
            link_flags.append("-undefined dynamic_lookup")

        to_compile = [ "vecdbImpl", "searchAlgorithm" ]

        cxx = "g++"

        writer.variable("CXX", cxx)
        writer.variable("CXX_FLAGS", " ".join(cxx_flags))
        writer.variable("LINK_FLAGS", " ".join(link_flags))

        writer.rule("compile", "$CXX -MMD -MF $out.d $CXX_FLAGS $in -c -o $out", depfile="$out.d", description="compile $out")
        for _m in to_compile:
            writer.build(os.path.join(BIN_DIR, f"{_m}.o"), "compile", os.path.join(SRC_DIR, f"{_m}.cpp"))
        
        writer.rule("link", "$CXX $LINK_FLAGS $in -o $out", description="link $out")
        writer.build(os.path.join(BIN_DIR, f"{module_name}{ext_suffix}"), "link", [os.path.join(BIN_DIR, f"{_m}.o") for _m in to_compile])

def _get_module_name(feat_dim):
    return f"vecdbImpl{feat_dim}"

def compile(feat_dim) -> str:
    _writeNinja(feat_dim)
    print("\033[1;30m", end="\r")
    print("----------------------------------------")
    subprocess.check_call(["ninja", "-t", "commands"], cwd = BUILD_DIR)
    print("----------------------------------------")
    subprocess.check_call("ninja", cwd = BUILD_DIR)
    with open(os.path.join(BUILD_DIR, "compile_commands.json"), "w") as f:
        # ninja -t compdb > compile_commands.json
        subprocess.check_call(["ninja", "-t", "compdb"], cwd = BUILD_DIR, stdout=f)
    print("\033[0m", end="\r")
    return _get_module_name(feat_dim)

    
    