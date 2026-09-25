import importlib.util
from pathlib import Path
import sys
import types

# Tests focus on mapper helpers and must also run on the Linux CI host.
if "pefile" not in sys.modules:
    fake=types.ModuleType("pefile")
    fake.DIRECTORY_ENTRY={"IMAGE_DIRECTORY_ENTRY_IMPORT":1,"IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT":13,"IMAGE_DIRECTORY_ENTRY_EXPORT":0,"IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR":14}
    fake.PEFormatError=ValueError
    fake.PE=object
    sys.modules["pefile"]=fake

MODULE_PATH=Path(__file__).parents[1]/"build_abi_map.py"
def load_module():
    spec=importlib.util.spec_from_file_location("gfyms_build_abi_map",MODULE_PATH)
    module=importlib.util.module_from_spec(spec);assert spec.loader is not None;spec.loader.exec_module(module);return module
loader=types.ModuleType("tools_gfyms_native_re_build_abi_map_loader");loader.load_module=load_module
sys.modules["tools.gfyms_native_re_build_abi_map_loader"]=loader
