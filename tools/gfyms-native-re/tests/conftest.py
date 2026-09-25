import importlib.util
from pathlib import Path
import sys
import types

MODULE_PATH=Path(__file__).parents[1]/"build_abi_map.py"

def load_module():
    spec=importlib.util.spec_from_file_location("gfyms_build_abi_map",MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

loader=types.ModuleType("tools_gfyms_native_re_build_abi_map_loader")
loader.load_module=load_module
sys.modules["tools_gfyms_native_re_build_abi_map_loader"]=loader
