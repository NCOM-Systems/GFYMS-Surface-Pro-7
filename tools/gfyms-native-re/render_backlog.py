#!/usr/bin/env python3
"""Render ABI-map v2 into a driver backlog CSV and Ghidra shortlist."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
KERNEL_MODULES={"ntoskrnl.exe","ntkrnlmp.exe","ntkrnlpa.exe","ntkrpamp.exe","hal.dll"}
DEFERRED_TOKENS=("ipu","sst")
DEFERRED_NAMES=("igdkmd64.sys",)

def load(path:Path)->dict:
    with path.open("r",encoding="utf-8") as f:return json.load(f)

def _hwid_count(record,infs):
    name=Path(record.get("path","")).name.casefold(); ids=set()
    for inf in infs:
        if name in {Path(x).name.casefold() for x in inf.get("referenced_binaries",[])}:
            ids.update(x.get("normalized_hwid","") for x in inf.get("hardware_ids",[]) if isinstance(x,dict))
    return len({x for x in ids if x})

def _nt_import_count(record):
    return sum(len(g.get("functions",[])) for k in ("imports","delay_imports") for g in record.get("dependencies",{}).get(k,[]) if g.get("module") in KERNEL_MODULES)

def _confidence(record):
    wdf=record.get("dependencies",{}).get("wdf",{})
    value=wdf.get("confidence")
    return float(value) if isinstance(value,(int,float)) else (1.0 if record.get("analysis_status")=="ok" else 0.0)

def rows(data):
    infs=data.get("infs",[]); out=[]
    for record in data.get("binaries",[]):
        if record.get("kind")!="sys":continue
        wdf=record.get("dependencies",{}).get("wdf",{}); runtime=record.get("dependencies",{}).get("runtime",{})
        out.append({"driver":record.get("path",""),"arch":record.get("architecture",""),"nt_imports":_nt_import_count(record),
                    "wdf_kind":wdf.get("kind",""),"delay":record.get("delay_import_symbol_count",0),
                    "runtime":runtime.get("kind",""),"hwid_count":_hwid_count(record,infs),
                    "confidence":f"{_confidence(record):.2f}","analysis_status":record.get("analysis_status","")})
    return out

def shortlist(rows_data,limit):
    if not 1<=limit<=15:raise ValueError("limit must be between 1 and 15")
    candidates=[]
    for row in rows_data:
        if row["analysis_status"]!="ok":continue
        wdf=row["wdf_kind"].lower()
        # Prefer drivers with no WDF, or a recovered WDF bind (0.90 heuristic).
        if wdf and float(row["confidence"]) < 0.9:continue
        name=row["driver"].casefold()
        deferred=any(name.endswith(x) for x in DEFERRED_NAMES) or any(x in name for x in DEFERRED_TOKENS)
        candidates.append((1 if deferred else 0,int(row["nt_imports"]),int(row["delay"]),name,row["driver"]))
    candidates.sort()
    return [x[-1] for x in candidates[:limit]]

def main():
    p=argparse.ArgumentParser();p.add_argument("abi_map",type=Path);p.add_argument("--output-csv",type=Path);p.add_argument("--shortlist",type=Path);p.add_argument("--limit",type=int,default=15);a=p.parse_args()
    data=load(a.abi_map); backlog=sorted(rows(data),key=lambda x:(x["nt_imports"],x["delay"],x["driver"].casefold()))
    out=a.output_csv or a.abi_map.with_name("backlog.csv");out.parent.mkdir(parents=True,exist_ok=True)
    fields=["driver","arch","nt_imports","wdf_kind","delay","runtime","hwid_count","confidence","analysis_status"]
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(backlog)
    shortlist_path=a.shortlist or a.abi_map.with_name("ghidra-shortlist.json");shortlist_path.parent.mkdir(parents=True,exist_ok=True)
    selected=shortlist(backlog,a.limit);shortlist_path.write_text(json.dumps(selected,indent=2)+"\n",encoding="utf-8")
    print(f"backlog: {out}");print(f"ghidra shortlist ({len(selected)}): {shortlist_path}")
    return 0
if __name__=="__main__":raise SystemExit(main())
