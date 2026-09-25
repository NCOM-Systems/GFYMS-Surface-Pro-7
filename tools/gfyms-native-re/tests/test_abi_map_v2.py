import csv
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.gfyms_native_re_build_abi_map_loader import load_module

module=load_module()

def write_table(root,name,fieldnames,rows):
    table_dir=root/"tables";table_dir.mkdir(parents=True,exist_ok=True)
    with (table_dir/f"{name}.csv").open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fieldnames);writer.writeheader();writer.writerows(rows)

def test_inf_parser_sections_strings_hwids_and_services(tmp_path):
    inf=tmp_path/"Surface.inf"
    inf.write_text("""[Version]\nSignature="$Windows NT$"\nClass=System\nProvider=%Provider%\n\n[Manufacturer]\n%Mfg%=Models,NTamd64\n\n[Models.NTamd64]\n%Device%=Install,PCI\\VEN_8086&DEV_9A13&SUBSYS_12345678&REV_01\n\n[Install.Services]\nAddService=SurfaceFoo,0x00000002,SurfaceFoo_Service\n\n[SurfaceFoo_Service]\nServiceBinary=%13%\\SurfaceFoo.sys\n\n[Strings]\nProvider="GFYMS"\nMfg="Microsoft"\nDevice="Surface Foo"\n""",encoding="utf-8")
    result=module.parse_inf(inf)
    assert result["strings"]["provider"]=="GFYMS"
    assert any(x["normalized_hwid"].startswith("PCI\\VEN_8086&DEV_9A13") for x in result["hardware_ids"])
    assert result["add_services"][0]["service_binary"]=="drivers\\SurfaceFoo.sys"
    assert "SurfaceFoo.sys" in result["referenced_binaries"]

def test_msi_directory_resolution_and_payload_paths(tmp_path):
    write_table(tmp_path,"Directory",["Directory","Directory_Parent","DefaultDir"],[
        {"Directory":"TARGETDIR","Directory_Parent":"","DefaultDir":"SourceDir"},
        {"Directory":"ProgramFiles64Folder","Directory_Parent":"TARGETDIR","DefaultDir":"."},
        {"Directory":"SurfaceUpdate","Directory_Parent":"ProgramFiles64Folder","DefaultDir":"SURFACE~1|Surface Update"},
        {"Directory":"DriverDir","Directory_Parent":"SurfaceUpdate","DefaultDir":".:Drivers"}])
    write_table(tmp_path,"Component",["Component","Directory_"],[{"Component":"cmp1","Directory_":"SurfaceUpdate"}])
    write_table(tmp_path,"File",["File","Component_","FileName","FileSize"],[{"File":"file1","Component_":"cmp1","FileName":"FOO~1.SYS|Foo.sys","FileSize":"42"}])
    for name,fields in [("Feature",["Feature"]),("FeatureComponents",["Feature_","Component_"]),("CustomAction",["Action","Type","Source","Target"]),("InstallExecuteSequence",["Action","Condition","Sequence"]),("Property",["Property","Value"]),("Media",["DiskId"]),("Binary",["Name"]),("ServiceInstall",["Name"]),("ServiceControl",["Name"]),("MsiAssembly",["Name"]),("MsiAssemblyName",["Name"])]:
        write_table(tmp_path,name,fields,[])
    result=module.parse_msi_tables(tmp_path)
    assert result["directories"]["SurfaceUpdate"]["source_relative_path"]=="Surface Update"
    assert result["directories"]["DriverDir"]["source_relative_path"]=="Surface Update/Drivers"
    assert result["payloads"][0]["source_relative_path"]=="Surface Update/Foo.sys"

def test_msi_payload_join_prefers_exact_path_and_uses_size_fallback(tmp_path):
    payloads=[{"file_id":"a","filename":"Foo.sys","size":"100","source_relative_path":"ProgramFiles64Folder/SurfaceUpdate/Foo.sys"},{"file_id":"b","filename":"Bar.sys","size":"200","source_relative_path":"missing/Bar.sys"}]
    pe_records=[{"path":"ProgramFiles64Folder/SurfaceUpdate/Foo.sys","size":100},{"path":"other/Bar.sys","size":200}]
    joins=module.join_msi_files(tmp_path,payloads,pe_records)
    assert joins[0]["confidence"]=="high";assert joins[1]["confidence"]=="medium"

def test_runtime_config_detects_netfx_sku(tmp_path):
    config=tmp_path/"IntelAudioService.exe.config"
    config.write_text('<configuration><startup><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.6.1"/></startup><system.serviceModel/></configuration>',encoding="utf-8")
    result=module._runtime_config_record(config);req=result["runtime_requirements"][0]
    assert req["family"]=="netfx" and req["runtime_version"]=="v4.0" and req["sku"]==".NETFramework,Version=v4.6.1" and req["version"]=="4.6.1"
    assert result["wcf"] is True

def test_empty_corpus_builds_v2(tmp_path):
    result=module.build(tmp_path,"v2")
    assert result["schema"]=="gfyms.surface.abi-map.v2" and result["inventory"]["pe_images"]==0

def test_render_contains_backlog_header(tmp_path):
    rendered=module.render_markdown(module.build(tmp_path,"v2"))
    assert "## Driver compatibility backlog" in rendered and "MSI→PE exact joins" in rendered

def test_runtimeconfig_json_is_modern_dotnet():
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/"Foo.runtimeconfig.json"
        p.write_text('{"runtimeOptions":{"tfm":"net8.0","framework":{"name":"Microsoft.NETCore.App","version":"8.0.0"}}}',encoding="utf-8")
        record=module._runtime_config(p)
        assert record["runtime_requirements"][0]["name"]=="Microsoft.NETCore.App"

def test_render_backlog_has_required_schema(tmp_path):
    render_path=Path(__file__).parents[1]/"render_backlog.py"
    spec=importlib.util.spec_from_file_location("gfyms_render_backlog",render_path)
    assert spec is not None and spec.loader is not None
    render=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)
    data={"binaries":[{"kind":"sys","path":"Foo.sys","architecture":"x86_64",
                      "analysis_status":"ok","import_symbol_count":2,"delay_import_symbol_count":0,
                      "dependencies":{"imports":[],"delay_imports":[],"wdf":{},"runtime":{}}}],
          "infs":[]}
    rows=render.rows(data)
    assert rows[0]["driver"]=="Foo.sys"
    assert render.shortlist(rows,15)==["Foo.sys"]
    abi_map=tmp_path/"abi-map.json";abi_map.write_text(json.dumps(data),encoding="utf-8")
    out_csv=tmp_path/"backlog.csv";out_json=tmp_path/"shortlist.json"
    argv_old=sys.argv[:]
    try:
        sys.argv=["render_backlog.py",str(abi_map),"--output-csv",str(out_csv),"--shortlist",str(out_json)]
        rc=render.main()
    finally:
        sys.argv=argv_old
    assert rc==0
    assert out_csv.read_text(encoding="utf-8").splitlines()[0].startswith("driver,arch,nt_imports")


def test_custom_action_type_flags_are_decoded_with_msi_semantics():
    flags = set(module._action_type(0x00000400 | 0x00000100 | 0x00000800 | 0x00004000)[2])
    assert flags == {"in-script", "rollback", "no-impersonate", "tsa-aware"}
    immediate = set(module._action_type(0x00000040 | 0x00000080 | 0x00000100 | 0x00000200 | 0x00002000)[2])
    assert immediate == {"continue", "async", "first-sequence", "once-per-process", "hide-target"}

def test_runtimeconfig_tfm_is_preserved_for_self_contained_app(tmp_path):
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/"Foo.runtimeconfig.json"
        p.write_text('{"runtimeOptions":{"tfm":"net8.0","includedFrameworks":[{"name":"Microsoft.NETCore.App","version":"8.0.1"}]}}',encoding="utf-8")
        record=module._runtime_config(p)
        assert record["self_contained"] is True
        assert record["runtime_requirements"][0]["target_framework"]=="net8.0"

def test_malformed_pe_is_reported_not_raised(tmp_path):
    p=tmp_path/"broken.sys"
    p.write_bytes(b"not-a-pe")
    record=module.parse_pe(p)
    assert record["analysis_status"]=="error"
    assert "PE" in record["analysis_error"] or "pe" in record["analysis_error"].lower()
