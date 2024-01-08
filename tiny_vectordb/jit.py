
# https://ninja-build.org/manual.html
from ninja import ninja_syntax
import pybind11
import os, sysconfig, subprocess, platform, sys
from .config import CACHE_DIR, SRC_DIR, HEADER_DIR, BUILD_DIR, BIN_DIR
from .jit_utils import initEigenSrc, checkCommandExists

eigen_version = "3.4.0"
eigen_src_path = os.path.join(CACHE_DIR, f"eigen{eigen_version}")
initEigenSrc(eigen_src_path, eigen_version)

def _writeNinja(
        feat_dim: int, 
        cxx = "g++", 
        additional_compile_flags = [],
        additional_link_flags = []
        ):
    if not checkCommandExists(cxx):
        raise RuntimeError(f"{cxx} not found.")

    module_name = _get_module_name(feat_dim)
    bin_dir = os.path.join(BIN_DIR, module_name)
    script_dir = os.path.join(BUILD_DIR, "scripts_"+ module_name)
    lib_dir = os.path.join(BIN_DIR, "lib")
    ninja_build_file = os.path.join(script_dir, "build.ninja")
    for _d in [bin_dir, lib_dir, script_dir]:
        if not os.path.exists(_d):
            os.makedirs(_d, exist_ok=True)

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    obj_suffix = ".obj" if platform.system() == "Windows" else ".o"
    py_includes = sysconfig.get_config_var('INCLUDEPY')

    with open(ninja_build_file, "w") as build_file:
        writer = ninja_syntax.Writer(build_file)
        writer.comment("This file is generated by build.py")

        to_compile = [ "vecdbImpl", ]
        to_compile_lib = [ "diskIO", "b64enc", "searchAlgorithm" ]

        if cxx == "g++" or cxx == "clang++":
            cxx_flags = [
                "-std=c++17",
                "-Wall",
                f"-I{eigen_src_path}",
                f"-I{py_includes}",
                f"-I{pybind11.get_include()}",
                f"-I{HEADER_DIR}",
                f"-DFEAT_DIM={feat_dim}",
                f"-DMODULE_NAME={module_name}",

                ## Optimization flags
                "-DNDEBUG",
                "-O2",
                "-funroll-loops",
            ] + additional_compile_flags

            if platform.system() == "Windows":
                cxx_flags += [ "-DYNAMICBASE" ]
            else:
                cxx_flags += [ "-fPIC" ]

            link_flags = [
                "-shared",
                "-lstdc++",
            ] + additional_link_flags
            if platform.system() == "Darwin":
                link_flags.append("-undefined dynamic_lookup")

            writer.variable("CXX", cxx)
            writer.variable("CXX_FLAGS", " ".join(cxx_flags))
            writer.variable("LINK_FLAGS", " ".join(link_flags))

            writer.rule("compile", "$CXX -MMD -MF $out.d $CXX_FLAGS $in -c -o $out", depfile="$out.d", description="compile $out")
            for _m in to_compile:
                writer.build(os.path.join(bin_dir, f"{_m}{feat_dim}{obj_suffix}"), "compile", os.path.join(SRC_DIR, f"{_m}.cpp"))
            for _m in to_compile_lib:
                writer.build(os.path.join(lib_dir, f"{_m}{obj_suffix}"), "compile", os.path.join(SRC_DIR, f"{_m}.cpp"))
            
            writer.rule("link", "$CXX $LINK_FLAGS $in -o $out", description="link $out")
            writer.build(os.path.join(bin_dir, f"{module_name}{ext_suffix}"), "link", \
                            [os.path.join(bin_dir, f"{_m}{feat_dim}{obj_suffix}") for _m in to_compile] + \
                            [os.path.join(lib_dir, f"{_m}{obj_suffix}") for _m in to_compile_lib])
        
        elif cxx == "cl" and platform.system() == "Windows":
            # TODO: to be implemented...
            ...

        else:
            raise NotImplementedError(f"Unsupported compiler: {cxx} in {platform.system()}")
        
    return module_name, script_dir, bin_dir

def _get_module_name(feat_dim):
    return f"vecdbImpl{feat_dim}"

def compile(
        feat_dim, 
        quite = False, 
        cxx: str = "g++",
        additional_compile_flags = [],
        additional_link_flags = []
        ) -> str:
    module_name, script_dir, bin_dir = _writeNinja(
        feat_dim, 
        cxx=cxx, 
        additional_compile_flags=additional_compile_flags, 
        additional_link_flags=additional_link_flags
        )

    def print_(*args, **kwargs):
        if not quite:
            print(*args, **kwargs)
    SP_STDOUT = subprocess.DEVNULL if quite else sys.stdout

    print_("\033[1;30m", end="\r")
    print_("----------------------------------------")

    subprocess.check_call(["ninja", "-t", "commands"], cwd = script_dir, stdout=SP_STDOUT)
    print_("----------------------------------------")

    subprocess.check_call("ninja", cwd = script_dir, stdout=SP_STDOUT)

    with open(os.path.join(script_dir, "compile_commands.json"), "w") as f:
        # ninja -t compdb > compile_commands.json
        subprocess.check_call(["ninja", "-t", "compdb"], cwd = script_dir, stdout=f, stderr=SP_STDOUT)

    print_("\033[0m", end="\r")
    return f"{bin_dir}.{module_name}".split(os.path.sep)[-1]