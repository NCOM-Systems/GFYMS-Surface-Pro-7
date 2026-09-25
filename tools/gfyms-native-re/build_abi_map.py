#!/usr/bin/env python3
"""Build the Surface Pro 7 Windows driver/runtime ABI dependency map.

v2 is a research mapper: it indexes PE/INF/MSI/runtime relationships and turns
host-provided Windows imports into explicit compatibility-ABI backlog nodes.
Vendor binaries are inputs only; this tool does not redistribute them.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

import pefile

LFS_PREFIX=b"version https://git-lfs.github.com/spec/v1"
PE_EXTENSIONS={".sys",".dll",".exe"}
KERNEL_MODULES={"ntoskrnl.exe","ntkrnlmp.exe","ntkrnlpa.exe","ntkrpamp.exe","hal.dll"}
WDF_MODULES={"wdfldr.sys","wdf01000.sys"}
HOST_MODULES=KERNEL_MODULES|WDF_MODULES|{
    "pci.sys","acpi.sys","ndis.sys","classpnp.sys","storport.sys","storahci.sys",
    "usbport.sys","usbhub.sys","usbccgp.sys","wmilib.sys",
}
HW_PREFIXES=("PCI\\","ACPI\\","USB\\","HID\\","I2C\\","SPI\\","UART\\","GPIO\\","SWD\\")


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def is_lfs_pointer(path:Path)->bool:
    try:
        with path.open("rb") as f:
            return f.read(len(LFS_PREFIX))==LFS_PREFIX
    except OSError:
        return False


def decode(value):
    if isinstance(value,bytes):
        return value.decode("utf-8","replace")
    return None if value is None else str(value)


def machine_name(machine:int)->str:
    return {0x014C:"x86",0x8664:"x86_64",0xAA64:"ARM64",0x01C4:"ARM",0xA641:"ARM64EC"}.get(machine,f"unknown-0x{machine:04x}")


def _groups(entries,kind):
    groups=[]
    for entry in entries:
        funcs=[]
        for item in getattr(entry,"imports",[]):
            funcs.append({"name":decode(getattr(item,"name",None)),
                          "ordinal":int(item.ordinal) if getattr(item,"ordinal",None) else None,
                          "hint":int(item.hint) if getattr(item,"hint",None) is not None else None})
        groups.append({"module":(decode(getattr(entry,"dll",None)) or "").lower(),"functions":funcs,"kind":kind})
    return groups


def _target_framework(raw:bytes):
    blobs=(raw.decode("utf-8","ignore"),raw.decode("utf-16le","ignore"))
    for blob in blobs:
        if "TargetFrameworkAttribute" not in blob:
            continue
        m=re.search(r"(?:\.NETFramework|\.NETCoreApp|\.NETStandard),Version=v[0-9.]+|net[0-9]+(?:\.[0-9]+)?",blob,re.I)
        if m:
            return m.group(0)
    return None


def _wdf_info(path:Path,pe,modules,imports):
    evidence=set()
    if modules&WDF_MODULES:
        evidence.add("wdf-module-import")
    if any((f["name"] or "").lower()=="wdfversionbind" or (f["name"] or "").lower().startswith("wdfldr")
           for g in imports for f in g["functions"]):
        evidence.add("WdfVersionBind")
    raw=path.read_bytes()
    marker="KmdfLibrary".encode("utf-16le")+b"\x00\x00"
    offsets=[m.start() for m in re.finditer(re.escape(marker),raw)]
    if offsets:
        evidence.add("KmdfLibrary")
    if not evidence:
        return {"kind":None,"confidence":0.0,"evidence":[]}
    ptr=8 if int(pe.FILE_HEADER.Machine) in {0x8664,0xAA64,0xA641} else 4
    expected=48 if ptr==8 else 32
    fmt="<Q" if ptr==8 else "<I"
    bind=None
    for off in offsets:
        try:
            string_rva=pe.get_rva_from_offset(off)
        except Exception:
            continue
        for candidate in range(max(0,off-256),min(len(raw)-expected,off+64),ptr):
            if struct.unpack_from("<I",raw,candidate)[0]!=expected:
                continue
            component=struct.unpack_from(fmt,raw,candidate+ptr)[0]
            if component not in {string_rva,int(pe.OPTIONAL_HEADER.ImageBase)+string_rva}:
                continue
            major,minor,build=struct.unpack_from("<III",raw,candidate+2*ptr)
            func_count=struct.unpack_from("<I",raw,candidate+2*ptr+12)[0]
            if 1<=major<=10 and 0<=minor<=99 and 0<=build<=100000 and 1<=func_count<=10000:
                bind={"bind_major":major,"bind_minor":minor,"bind_build":build,
                      "func_count":func_count,"bind_info_offset":candidate,"component_rva":string_rva}
                break
        if bind:
            break
    result={"kind":"kmdf",
            "confidence":0.9 if bind else (0.6 if "WdfVersionBind" in evidence else 0.75),
            "evidence":sorted(evidence)}
    if bind:
        result.update(bind)
        result["evidence"]=sorted(evidence|{"WDF_BIND_INFO"})
    return result


def parse_pe(path:Path)->dict:
    rec={"path":path.as_posix(),"size":path.stat().st_size,"sha256":sha256(path),
         "lfs_pointer":is_lfs_pointer(path),"kind":path.suffix.lower().lstrip(".")}
    if rec["lfs_pointer"]:
        rec["analysis_status"]="git-lfs-pointer"
        rec["dependencies"]={"imports":[],"delay_imports":[],"exports":[],"wdf":{},"runtime":{}}
        return rec
    try:
        pe=pefile.PE(str(path),fast_load=False)
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR"],
        ])
        imports=_groups(getattr(pe,"DIRECTORY_ENTRY_IMPORT",[]),"import")
        delay=_groups(getattr(pe,"DIRECTORY_ENTRY_DELAY_IMPORT",[]),"delay-import")
        exports=[{"name":decode(x.name),"ordinal":int(x.ordinal),"address":int(x.address),
                  "forwarder":decode(getattr(x,"forwarder",None))}
                 for x in getattr(getattr(pe,"DIRECTORY_ENTRY_EXPORT",None),"symbols",[])]
        clr=pe.OPTIONAL_HEADER.DATA_DIRECTORY[14]
        modules={g["module"] for g in imports}
        runtime={"managed_image":bool(clr.VirtualAddress and clr.Size),"evidence":[]}
        for g in imports:
            if g["module"]=="mscoree.dll":
                for f in g["functions"]:
                    if (f["name"] or "").lower() in {"_corexemain","_cordllmain","_corexemain@16"}:
                        runtime["evidence"].append("mscoree.dll!"+(f["name"] or ""))
        if runtime["managed_image"]:
            runtime["evidence"].append("CLR_DIRECTORY")
        tfm=_target_framework(path.read_bytes())
        if tfm:
            runtime["target_framework"]=tfm
            runtime["evidence"].append("TargetFrameworkAttribute")
            runtime["kind"]="dotnet-framework" if tfm.lower().startswith(".netframework") else "dotnet-modern"
        runtime["evidence"]=sorted(set(runtime["evidence"]))
        if "kind" not in runtime:
            runtime["kind"]="managed-image" if runtime["managed_image"] else None
        rec.update({
            "analysis_status":"ok","architecture":machine_name(int(pe.FILE_HEADER.Machine)),
            "machine":f"0x{int(pe.FILE_HEADER.Machine):04x}",
            "entry_point_rva":int(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
            "image_base":hex(int(pe.OPTIONAL_HEADER.ImageBase)),
            "subsystem":int(pe.OPTIONAL_HEADER.Subsystem),
            "clr":{"present":bool(clr.VirtualAddress and clr.Size),"directory_rva":hex(int(clr.VirtualAddress)),
                   "directory_size":int(clr.Size)},
            "imports":imports,"delay_imports":delay,"exports":exports,
            "import_modules":sorted(modules),"delay_import_modules":sorted(g["module"] for g in delay),
            "import_symbol_count":sum(len(g["functions"]) for g in imports),
            "delay_import_symbol_count":sum(len(g["functions"]) for g in delay),
            "export_symbol_count":len(exports),
            "dependencies":{"imports":imports,"delay_imports":delay,"exports":exports,
                            "wdf":_wdf_info(path,pe,modules,imports),"runtime":runtime},
        })
    except (pefile.PEFormatError,OSError,ValueError,struct.error) as exc:
        rec["analysis_status"]="error"
        rec["analysis_error"]=str(exc)
    return rec


def _join_inf_lines(lines):
    out=[]; buf=""
    for raw in lines:
        line=raw.split(";",1)[0].rstrip()
        if not line.strip():
            continue
        buf=buf+line.lstrip() if buf else line.strip()
        if buf.endswith(","):
            continue
        out.append(buf); buf=""
    if buf:
        out.append(buf)
    return out


def _expand_inf(value,strings):
    value=re.sub(r"%([^%]+)%",lambda m:strings.get(m.group(1).lower(),m.group(0)),value)
    for token,replacement in {"%01%":"source","%10%":"windows","%11%":"system32","%12%":"drivers","%13%":"drivers"}.items():
        value=re.sub(re.escape(token),replacement,value,flags=re.I)
    return value


def _hwids(value):
    out=[]
    for token in re.split(r"[,\s]+",value):
        token=token.strip().strip('"')
        up=token.upper()
        if up.startswith(HW_PREFIXES) or re.search(r"(?:^|[\\&])(?:VEN|DEV|VID|PID|SUBSYS|REV)_[0-9A-F]{2,8}(?:$|[&\\])",up):
            out.append(token)
    return out


def parse_inf(path:Path)->dict:
    raw=path.read_text(encoding="utf-8-sig",errors="replace").splitlines()
    lines=_join_inf_lines(raw)
    sections=defaultdict(list); current=""
    for line in lines:
        m=re.match(r"^\[([^\]]+)\]$",line.strip())
        if m:
            current=m.group(1).strip(); sections[current].append(line); continue
        if current:
            sections[current].append(line)
    strings={}
    for sec,vals in sections.items():
        if sec.lower()=="strings":
            for line in vals[1:]:
                if "=" in line:
                    k,v=line.split("=",1); strings[k.strip().lower()]=v.strip().strip('"')
    hardware={}; adds=[]; services={}; includes=set(); refs=set(); version={}
    for sec,vals in sections.items():
        low=sec.lower()
        for line in vals[1:]:
            expanded=_expand_inf(line,strings)
            if "=" not in expanded:
                continue
            key,value=expanded.split("=",1); key=key.strip(); value=value.strip()
            if low=="version":
                version[key.lower()]=value.strip('"')
            for hid in _hwids(value):
                hardware[hid.upper()]={"raw_hwid":hid,"normalized_hwid":hid.upper(),"section":sec}
            refs.update(re.findall(r"(?i)\b[A-Za-z0-9_.$()%-]+\.(?:sys|dll|exe)\b",value))
            if key.lower()=="include":
                includes.update(x.strip() for x in value.split(",") if x.strip())
            if key.lower()=="addservice":
                parts=[x.strip() for x in value.split(",")]
                adds.append({"service":parts[0] if parts else "","flags":parts[1] if len(parts)>1 else "",
                              "install_section":parts[2] if len(parts)>2 else "","section":sec})
            if key.lower()=="servicebinary":
                services.setdefault(sec,{})["service_binary"]=_expand_inf(value.strip('"'),strings)
    for add in adds:
        svc=services.get(add["install_section"],{})
        if svc.get("service_binary"):
            add["service_binary"]=svc["service_binary"]
            refs.add(Path(svc["service_binary"]).name)
    return {"path":path.as_posix(),"sha256":sha256(path),
            "sections":{k:v[1:] for k,v in sections.items()},"strings":strings,"version":version,
            "hardware_ids":sorted(hardware.values(),key=lambda x:x["normalized_hwid"]),
            "add_services":adds,"service_install_sections":services,"includes":sorted(includes),
            "referenced_binaries":sorted(refs),"raw_lines":lines}


def read_table(root:Path,name:str)->list[dict[str,str]]:
    p=root/"tables"/f"{name}.csv"
    if not p.is_file():
        return []
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def _directory_paths(rows):
    rows_by_id={r.get("Directory",""):r for r in rows}
    memo={}
    def resolve(did,seen=None):
        if not did or did not in rows_by_id:
            return ""
        if did in memo:
            return memo[did]
        seen=set() if seen is None else seen
        if did in seen:
            return ""
        seen.add(did)
        row=rows_by_id[did]
        raw=(row.get("DefaultDir","") or "").split("|",1)[-1]
        if did.upper()=="TARGETDIR" or raw.lower()=="sourcedir":
            name=""
        elif raw==".":
            name=""
        else:
            name=raw
        parent=resolve(row.get("Directory_Parent",""),seen)
        memo[did]="/".join(x for x in (parent,name) if x).strip("/")
        return memo[did]
    return {did:resolve(did) for did in rows_by_id}

def _action_type(value):
    try:
        typ=int(value or 0)
    except ValueError:
        typ=0
    base=typ&0x3f
    flags=[]
    for bit,label in ((0x0800,"async"),(0x1000,"rollback"),(0x2000,"commit"),(0x4000,"64bit-script")):
        if typ&bit:
            flags.append(label)
    return typ,base,flags


def parse_msi_tables(root:Path)->dict:
    names=["Directory","Feature","FeatureComponents","Component","File","CustomAction","InstallExecuteSequence",
           "Property","Media","Binary","ServiceInstall","ServiceControl","MsiAssembly","MsiAssemblyName"]
    tables={name:read_table(root,name) for name in names}
    product={r.get("Property",""):r.get("Value","") for r in tables["Property"] if r.get("Property")}
    dpaths=_directory_paths(tables["Directory"])
    component_dirs={r.get("Component",""):r.get("Directory_","") for r in tables["Component"] if r.get("Component")}
    payloads=[]
    for row in tables["File"]:
        raw=row.get("FileName",""); name=raw.split("|",1)[-1]
        directory=row.get("Directory_","") or component_dirs.get(row.get("Component_",""),"")
        payloads.append({"file_id":row.get("File",""),"component":row.get("Component_",""),"directory":directory,
                         "filename":name,"raw_filename":raw,
                         "source_relative_path":"/".join(x for x in (dpaths.get(directory,""),name) if x),
                         "version":row.get("Version",""),"language":row.get("Language",""),
                         "size":row.get("FileSize",""),"sequence":row.get("Sequence","")})
    actions=[]
    for row in tables["CustomAction"]:
        typ,base,flags=_action_type(row.get("Type","")); source=row.get("Source",""); target=row.get("Target","")
        low=target.lower()
        kind="driver-install-command" if ("pnputil" in low or "powershell" in low) else "custom-action" if source or base in {1,17} else "other"
        actions.append({"action":row.get("Action",""),"type":row.get("Type",""),"type_base":base,"type_flags":flags,
                        "source":source,"target":target,"kind":kind})
    directories={did:{"source_relative_path":path} for did,path in dpaths.items()}
    return {"product":product,"tables":tables,"directories":directories,"directory_paths":dpaths,
            "features":tables["Feature"],
            "feature_components":[{"feature":r.get("Feature_",""),"component":r.get("Component_","")} for r in tables["FeatureComponents"]],
            "components":tables["Component"],"payloads":payloads,"custom_actions":actions,
            "execute_sequence":tables["InstallExecuteSequence"],"media":tables["Media"],"binary_table":tables["Binary"],
            "driver_install_actions":[x for x in actions if x["kind"]=="driver-install-command"],
            "summary":{"feature_count":len(tables["Feature"]),"component_count":len(tables["Component"]),
                       "file_count":len(payloads),"custom_action_count":len(actions),
                       "driver_install_action_count":sum(x["kind"]=="driver-install-command" for x in actions)}}


def _size(value):
    try:return int(value)
    except (TypeError,ValueError):return None


def join_msi_files(*args):
    if len(args)==2:
        payloads,pe_records=args
    elif len(args)==3:
        _,payloads,pe_records=args
    else:
        raise TypeError("join_msi_files expects payloads, pe_records or root, payloads, pe_records")
    by_path=defaultdict(list); by_name=defaultdict(list)
    for p in pe_records:
        by_path[p["path"].casefold()].append(p)
        by_name[Path(p["path"]).name.casefold()].append(p)
    joins=[]
    for row in payloads:
        wanted=row["source_relative_path"].casefold()
        exact=by_path.get(wanted,[])
        if len(exact)==1:
            joins.append({"file_id":row["file_id"],"pe_path":exact[0]["path"],"confidence":"high","evidence":["directory-resolved-path"]})
            continue
        # Extraction trees commonly retain MSI logical roots such as ProgramFiles64Folder.
        parts=wanted.split("/")
        suffixes=["/".join(parts[i:]) for i in range(1,len(parts))]
        for suffix in suffixes:
            candidates=by_path.get(suffix,[])
            if len(candidates)==1:
                joins.append({"file_id":row["file_id"],"pe_path":candidates[0]["path"],"confidence":"high","evidence":["directory-resolved-path","extraction-root-suffix"]})
                break
        else:
            candidates=by_name.get(Path(row["filename"]).name.casefold(),[])
            size=_size(row.get("size"))
            sized=[p for p in candidates if size is not None and p.get("size")==size]
            if len(sized)==1:
                joins.append({"file_id":row["file_id"],"pe_path":sized[0]["path"],"confidence":"medium","evidence":["basename+size"]})
            elif len(candidates)==1:
                joins.append({"file_id":row["file_id"],"pe_path":candidates[0]["path"],"confidence":"low","evidence":["basename-collision-risk"]})
    return joins

def _runtime_config(path:Path)->dict:
    raw=path.read_text(encoding="utf-8-sig",errors="replace")
    rec={"path":path.as_posix(),"sha256":sha256(path),"size":path.stat().st_size,
         "kind":"runtimeconfig" if path.name.lower().endswith(".runtimeconfig.json") else "deps" if path.name.lower().endswith(".deps.json") else "legacy-netfx-config",
         "runtime_requirements":[],"evidence":[]}
    if path.name.lower().endswith(".exe.config"):
        runtime_versions=sorted(set(re.findall(r"<supportedRuntime[^>]*?version\s*=\s*[\"']([^\"']+)",raw,re.I)))
        skus=sorted(set(re.findall(r"sku\s*=\s*[\"']([^\"']+)",raw,re.I)))
        versions=sorted(set(re.findall(r"\.NETFramework,Version=v([^\"'<>]+)",raw,re.I)))
        if versions:
            rec["runtime_requirements"]=[{"family":"netfx","runtime_version":runtime_versions[0] if runtime_versions else None,
                                          "sku":skus[0] if skus else None,"version":versions[-1]}]
            rec["evidence"].append("supportedRuntime-sku")
        elif re.search(r"<supportedRuntime\b",raw,re.I):
            rec["runtime_requirements"]=[{"family":"netfx","runtime_version":runtime_versions[0] if runtime_versions else None,
                                          "sku":skus[0] if skus else None}]; rec["evidence"].append("supportedRuntime")
        rec["wcf"]="system.serviceModel" in raw
        if rec["wcf"]:
            rec["evidence"].append("system.serviceModel")
        return rec
    try:data=json.loads(raw)
    except json.JSONDecodeError as exc:
        rec.update({"analysis_status":"invalid-json","error":str(exc)}); return rec
    options=data.get("runtimeOptions",{}) if isinstance(data,dict) else {}
    req=[]
    if isinstance(options.get("framework"),dict):req.append(options["framework"])
    req.extend(x for x in options.get("frameworks",[]) if isinstance(x,dict))
    rec["runtime_requirements"]=req; rec["self_contained"]=bool(options.get("includedFrameworks")); rec["evidence"].append("runtimeOptions")
    return rec


def _runtime_config_record(path:Path)->dict:
    return _runtime_config(path)


def detect_runtime_requirements(pe_records,config_records):
    by_path={r["path"].casefold():r for r in config_records}
    by_name=defaultdict(list)
    for r in config_records:
        by_name[Path(r["path"]).name.casefold()].append(r)
    pe_by_path={r["path"].casefold():r for r in pe_records}
    for pe in pe_records:
        runtime=pe.setdefault("dependencies",{}).setdefault("runtime",{})
        pe_path=Path(pe["path"])
        candidates=[
            by_path.get((pe_path.parent/(pe_path.name+".config")).as_posix().casefold()),
            by_path.get((pe_path.parent/(pe_path.stem+".runtimeconfig.json")).as_posix().casefold()),
            by_path.get((pe_path.parent/(pe_path.stem+".deps.json")).as_posix().casefold()),
        ]
        cfg=next((x for x in candidates if x),None)
        if cfg is None:
            names=[(pe_path.name+".config"),(pe_path.stem+".runtimeconfig.json"),(pe_path.stem+".deps.json")]
            cfg=next((x for n in names for x in by_name.get(n.casefold(),[]) if x),None)
        if cfg:
            req=cfg.get("runtime_requirements",[])
            if req:
                runtime["config"]=cfg["path"]
                runtime["requirements"]=req
                runtime["evidence"]=sorted(set(runtime.get("evidence",[]))|set(cfg.get("evidence",[])))
                runtime["kind"]="dotnet-framework" if any(x.get("family")=="netfx" for x in req) else "dotnet-modern"
            if cfg.get("wcf"):
                runtime["wcf"]=True
        if pe["kind"]=="exe":
            sidecar=(pe_path.with_suffix(".dll")).as_posix()
            dll=pe_by_path.get(sidecar.casefold())
            if runtime.get("kind") is None and dll and dll.get("dependencies",{}).get("runtime",{}).get("managed_image"):
                runtime.update({"kind":"dotnet-apphost","evidence":sorted(set(runtime.get("evidence",[]))|{"managed-sidecar-dll"})})
        if runtime.get("kind"):
            runtime["confidence"]=0.9 if runtime.get("requirements") or runtime.get("evidence") else 0.6

def _edge_unique(edges):
    out=[]; seen=set()
    for e in edges:
        key=(e.get("from"),e.get("to"),e.get("type"),e.get("confidence"),tuple(e.get("evidence",())))
        if key not in seen:
            seen.add(key); out.append(e)
    return out


def build(root:Path,schema="v2")->dict:
    if schema not in {"v1","v2"}:
        raise ValueError(f"Unsupported schema: {schema}")
    files=[p for p in root.rglob("*") if p.is_file()]
    pe_records=[]; by_name=defaultdict(list)
    for p in files:
        if p.suffix.lower() not in PE_EXTENSIONS: continue
        r=parse_pe(p); r["path"]=p.relative_to(root).as_posix()
        r["runtime_class"]="windows-kernel-driver" if p.suffix.lower()==".sys" else "dotnet-managed" if r.get("dependencies",{}).get("runtime",{}).get("kind") else "native-win32"
        pe_records.append(r); by_name[p.name.casefold()].append(r)
    inf_records=[]
    for p in files:
        if p.suffix.lower()==".inf":
            r=parse_inf(p); r["path"]=p.relative_to(root).as_posix(); inf_records.append(r)
    configs=[]
    for p in files:
        if p.name.lower().endswith((".exe.config",".runtimeconfig.json",".deps.json")):
            r=_runtime_config(p); r["path"]=p.relative_to(root).as_posix(); configs.append(r)
    detect_runtime_requirements(pe_records,configs)
    for r in pe_records:
        if r.get("dependencies",{}).get("runtime",{}).get("kind"):
            r["runtime_class"]="dotnet-managed"
    msi=parse_msi_tables(root)
    joins=join_msi_files(msi["payloads"],pe_records)
    nodes=[]; edges=[]; node_seen=set()
    def add_node(item):
        if item["id"] not in node_seen:
            node_seen.add(item["id"]); nodes.append(item)
    for r in pe_records:
        source="pe:"+r["path"]; add_node({"id":source,"type":r["runtime_class"],"path":r["path"]})
        deps=r.get("dependencies",{})
        for group in deps.get("imports",[])+deps.get("delay_imports",[]):
            edge_type="delay-import" if group["kind"]=="delay-import" else "import"
            for f in group["functions"]:
                module=group["module"]; symbol=f["name"] or "#"+str(f["ordinal"])
                local=by_name.get(module,[])
                if local:
                    for target in local: edges.append({"from":source,"to":"pe:"+target["path"],"type":edge_type})
                else:
                    aid=f"abi:{module}!{symbol}"
                    add_node({"id":aid,"type":"host-abi" if module in HOST_MODULES else "external-import",
                              "module":module,"symbol":symbol,"local_binary":False,
                              "implementation_status":"unimplemented" if module in HOST_MODULES else "external"})
                    edges.append({"from":source,"to":aid,"type":edge_type})
        wdf=deps.get("wdf",{})
        if wdf.get("kind"):
            aid="abi:wdf:kmdf"; add_node({"id":aid,"type":"host-abi","provider":"wdf","kind":"kmdf","implementation_status":"unimplemented"})
            edges.append({"from":source,"to":aid,"type":"requires-wdf","confidence":wdf.get("confidence"),"evidence":wdf.get("evidence",[])})
        runtime=deps.get("runtime",{})
        for req in runtime.get("requirements",[]):
            fam=req.get("family") or req.get("name") or "runtime"
            version=req.get("version") or req.get("runtime_version") or req.get("target_framework") or ",".join(req.get("versions",[])) or "unknown"
            rid=f"runtime:{fam}:{version}"
            add_node({"id":rid,"type":"runtime-requirement",**req})
            edges.append({"from":source,"to":rid,"type":"requires-runtime","confidence":runtime.get("confidence",0.6),"evidence":runtime.get("evidence",[])})
    for inf in inf_records:
        iid="inf:"+inf["path"]; add_node({"id":iid,"type":"windows-inf","path":inf["path"]})
        for add in inf.get("add_services",[]):
            target=add.get("service_binary")
            if not target: continue
            for p in by_name.get(Path(target).name.casefold(),[]):
                edges.append({"from":iid,"to":"pe:"+p["path"],"type":"service-binds"})
    feature_ids={r.get("Feature","") for r in msi["features"] if r.get("Feature")}
    comp_ids={r.get("Component","") for r in msi["components"] if r.get("Component")}
    comp_files=defaultdict(list)
    for p in msi["payloads"]:
        if p["file_id"]:
            comp_files[p["component"]].append(p["file_id"])
            add_node({"id":"msi:file:"+p["file_id"],"type":"msi-file","name":p["filename"],"component":p["component"]})
    for f in feature_ids:add_node({"id":"msi:feature:"+f,"type":"msi-feature","name":f})
    for c in comp_ids:add_node({"id":"msi:component:"+c,"type":"msi-component","name":c})
    for rel in msi["feature_components"]:
        f,c=rel["feature"],rel["component"]
        if f in feature_ids and c in comp_ids: edges.append({"from":"msi:feature:"+f,"to":"msi:component:"+c,"type":"feature-component"})
        for fid in comp_files.get(c,[]): edges.append({"from":"msi:component:"+c,"to":"msi:file:"+fid,"type":"component-file"})
    for join in joins:
        edges.append({"from":"msi:file:"+join["file_id"],"to":"pe:"+join["pe_path"],"type":"payload-pe","confidence":join["confidence"],"evidence":join["evidence"]})
    binary_names={r.get("Name","") for r in msi["binary_table"] if r.get("Name")}
    for action in msi["custom_actions"]:
        aid="msi:custom-action:"+action["action"]; add_node({"id":aid,"type":"msi-custom-action",**action})
        source=action["source"]
        if source in binary_names:
            bid="msi:binary:"+source; add_node({"id":bid,"type":"msi-binary","name":source})
            edges.append({"from":aid,"to":bid,"type":"custom-action-binary"})
    module_counts=Counter(); delay_counts=Counter(); kernel_counts=Counter(); wdf_counts=Counter()
    for r in pe_records:
        module_counts.update(r.get("import_modules",[])); delay_counts.update(r.get("delay_import_modules",[]))
        for g in r.get("dependencies",{}).get("imports",[])+r.get("dependencies",{}).get("delay_imports",[]):
            for f in g["functions"]:
                name=f["name"] or "#"+str(f["ordinal"])
                if g["module"] in KERNEL_MODULES: kernel_counts[g["module"]+"!"+name]+=1
                if g["module"] in WDF_MODULES: wdf_counts[g["module"]+"!"+name]+=1
    dup=defaultdict(list)
    for r in pe_records: dup[r["sha256"]].append(r["path"])
    jstats=Counter(x["confidence"] for x in joins)
    inventory={"files":len(files),"pe_images":len(pe_records),"sys":sum(x["kind"]=="sys" for x in pe_records),
               "dll":sum(x["kind"]=="dll" for x in pe_records),"exe":sum(x["kind"]=="exe" for x in pe_records),
               "inf":len(inf_records),"runtime_config":len(configs),"msi":sum(x.suffix.lower()==".msi" for x in files),
               "lfs_pointer_pe_images":sum(bool(x.get("lfs_pointer")) for x in pe_records),
               "pe_analysis_errors":sum(x.get("analysis_status")=="error" for x in pe_records),
               "msi_directory_rows":len(msi["tables"].get("Directory",[])),
               "msi_file_pe_joins_high":jstats["high"],"msi_file_pe_joins_medium":jstats["medium"],
               "msi_file_pe_joins_low":jstats["low"],"msi_file_pe_unmatched":len(msi["payloads"])-len(joins)}
    data={"schema":"gfyms.surface.abi-map.v2" if schema=="v2" else "gfyms.surface.abi-map.v1-compat",
          "inventory":inventory,"binaries":pe_records,"infs":inf_records,"runtime_metadata":configs,
          "dotnet_apps":[{"path":r["path"],"architecture":r.get("architecture"),"runtime":r["dependencies"].get("runtime",{})}
                         for r in pe_records if r.get("dependencies",{}).get("runtime",{}).get("kind")],
          "msi":msi,"msi_file_pe_joins":joins,"import_module_counts":module_counts.most_common(),
          "delay_import_module_counts":delay_counts.most_common(),"kernel_imports":kernel_counts.most_common(),
          "wdf_imports":wdf_counts.most_common(),"duplicate_hashes":{k:v for k,v in dup.items() if len(v)>1},
          "dependency_graph":{"nodes":nodes,"edges":_edge_unique(edges)}}
    return data


def render_markdown(data:dict)->str:
    inv=data["inventory"]; lines=["# GFYMS Surface Pro 7 ABI Map v2","",
        "Generated from a local extracted corpus. Research-only artifact; vendor binaries are not redistributed by this report.","",
        "## Inventory",""]
    labels=[("files","Files"),("pe_images","PE images"),("sys","SYS"),("dll","DLL"),("exe","EXE"),("inf","INF"),
            ("runtime_config","Runtime configs"),("msi","MSI"),("lfs_pointer_pe_images","Unresolved Git-LFS PE pointers"),
            ("pe_analysis_errors","PE analysis errors"),("msi_directory_rows","MSI Directory rows"),
            ("msi_file_pe_joins_high","MSI→PE exact joins"),("msi_file_pe_joins_medium","MSI→PE size-assisted joins"),
            ("msi_file_pe_joins_low","MSI→PE low-confidence joins"),("msi_file_pe_unmatched","MSI payloads unmatched")]
    lines += [f"- {label}: {inv.get(key,0)}" for key,label in labels]
    lines += ["","## Driver compatibility backlog","",
              "| Driver | Arch | NT imports | WDF | Delay | Runtime | HWIDs | Confidence |",
              "|---|---|---:|---|---:|---|---:|---:|"]
    for r in sorted((x for x in data["binaries"] if x["kind"]=="sys"),key=lambda x:(x.get("import_symbol_count",10**9),x["path"].lower())):
        deps=r.get("dependencies",{}); nt=sum(len(g["functions"]) for g in deps.get("imports",[])+deps.get("delay_imports",[]) if g["module"] in KERNEL_MODULES)
        wdf=deps.get("wdf",{}); rt=deps.get("runtime",{}); name=Path(r["path"]).name.casefold(); hw=set()
        for inf in data["infs"]:
            if name in {Path(x).name.casefold() for x in inf.get("referenced_binaries",[])}:
                hw.update(x["normalized_hwid"] for x in inf.get("hardware_ids",[]))
        conf=float(wdf.get("confidence",1.0 if r.get("analysis_status")=="ok" else 0.0))
        lines.append(f"| `{r['path']}` | {r.get('architecture','?')} | {nt} | {wdf.get('kind') or '—'} | {r.get('delay_import_symbol_count',0)} | {rt.get('kind') or '—'} | {len(hw)} | {conf:.2f} |")
    lines += ["","## NT kernel ABI backlog","","| Symbol | References |","|---|---:|"]+[f"| `{n}` | {c} |" for n,c in data["kernel_imports"][:200]]
    lines += ["","## WDF ABI backlog","","| Symbol | References |","|---|---:|"]+[f"| `{n}` | {c} |" for n,c in data["wdf_imports"][:200]]
    lines += ["","## MSI → PE joins","","| MSI File | PE | Confidence | Evidence |","|---|---|---|---|"]+[f"| `{j['file_id']}` | `{j['pe_path']}` | {j['confidence']} | {', '.join(j['evidence'])} |" for j in data.get("msi_file_pe_joins",[])]
    return "\n".join(lines)+"\n"


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    p.add_argument("-o","--output",type=Path,default=Path("abi-map.json"))
    p.add_argument("--markdown",type=Path,default=Path("abi-map.md"))
    p.add_argument("--schema",choices=("v1","v2"),default="v2")
    args=p.parse_args()
    root=args.root.resolve()
    if not root.is_dir(): raise SystemExit(f"Not a directory: {root}")
    data=build(root,args.schema)
    args.output.parent.mkdir(parents=True,exist_ok=True); args.markdown.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    args.markdown.write_text(render_markdown(data),encoding="utf-8")
    print(json.dumps(data["inventory"],indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
