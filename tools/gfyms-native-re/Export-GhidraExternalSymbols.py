# Ghidra postScript: export imported/external symbols for the current program.
from ghidra.app.script import GhidraScript
import json
import os

class ExportGhidraExternalSymbols(GhidraScript):
    def run(self):
        args=self.getScriptArgs()
        if not args:
            raise RuntimeError("result JSON path is required")
        output_path=os.path.abspath(args[0])
        symbol_names=set()
        function_names=set()
        for symbol in self.getCurrentProgram().getSymbolTable().getAllSymbols(True):
            name=symbol.getName()
            if symbol.isExternal() or symbol.getSource().name=="IMPORTED":
                symbol_names.add(name)
        manager=self.getCurrentProgram().getExternalManager()
        for library in manager.getExternalLibraryNames():
            for location in manager.getExternalLocations(library):
                function_names.add(location.getLabel())
        payload={
            "program":self.getCurrentProgram().getName(),
            "image_base":str(self.getCurrentProgram().getImageBase()),
            "external_symbols":sorted(symbol_names),
            "external_functions":sorted(function_names),
        }
        parent=os.path.dirname(output_path)
        if parent:
            os.makedirs(parent,exist_ok=True)
        with open(output_path,"w",encoding="utf-8") as handle:
            json.dump(payload,handle,indent=2)
