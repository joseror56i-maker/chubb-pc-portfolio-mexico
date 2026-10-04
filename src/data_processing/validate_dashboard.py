"""Check project dependencies and report bindings; this is not a DAX/refresh engine."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def validate_dashboard(project_path):
    """Detect missing folders/assets, invalid JSON and broken table/field bindings.

    Source evidence is static. PASS does not mean Desktop opened, refreshed or
    evaluated measures successfully. Cache and machine settings must stay private.
    """
    project_path = Path(project_path)
    issues = Counter()
    root = project_path.parent.resolve()
    def inside(base, relative):
        path = (base / relative).resolve()
        if path != root and root not in path.parents:
            raise ValueError("Dependency escapes dashboard project directory")
        return path
    try:
        project = json.loads(project_path.read_text(encoding="utf-8-sig"))
        report = inside(root, project["artifacts"][0]["report"]["path"])
        report_definition = json.loads((report / "definition.pbir").read_text(encoding="utf-8-sig"))
        model = inside(report, report_definition["datasetReference"]["byPath"]["path"])
        if not (model / "definition.pbism").is_file():
            raise ValueError("Missing semantic model definition")
    except (OSError, ValueError, KeyError, IndexError) as error:
        return {"status": "FAIL", "scope": "static_project_dependencies", "issues": {"project_reference": 1},
                "detail": str(error), "desktop_refresh_tested": False}
    json_files = {}
    for path in (*report.rglob("*.json"), *model.rglob("*.json")):
        if ".pbi" in path.parts:
            continue
        try:
            json_files[path] = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            issues["invalid_json"] += 1
    for path in (*report.rglob("*"), *model.rglob("*")):
        if path.name in {"cache.abf", "localSettings.json", "unappliedChanges.json"}:
            issues["private_or_unapplied_state_in_package"] += 1
    tables = {}
    for path in (model / "definition/tables").glob("*.tmdl"):
        text = path.read_text(encoding="utf-8-sig")
        name = re.search(r"^table (.+)$", text, re.MULTILINE)
        if name:
            measures = {match.strip("'").replace("''", "'") for match in re.findall(
                r"^\tmeasure ('(?:[^']|'')+'|[^\s=]+)\s*=", text, re.MULTILINE)}
            columns = {match.strip("'").replace("''", "'") for match in re.findall(
                r"^\tcolumn ('(?:[^']|'')+'|[^\s=]+)", text, re.MULTILINE)}
            tables[name.group(1).strip("'")] = {"Measure": measures, "Column": columns}
    pages_definition = report / "definition/pages/pages.json"
    pages = json_files.get(pages_definition, {})
    for name in pages.get("pageOrder", []):
        if not (report / "definition/pages" / name / "page.json").is_file():
            issues["missing_page"] += 1
    definitions = json_files.get(report / "definition/report.json", {})
    resources = {}
    for package in definitions.get("resourcePackages", []):
        for item in package.get("items", []):
            asset = report / "StaticResources" / package["name"] / item["path"]
            resources[(package["name"], item["name"])] = asset
            if not asset.is_file():
                issues["missing_registered_resource"] += 1
    visuals = 0
    for path, value in json_files.items():
        if path.name == "visual.json":
            visuals += 1
        for node in walk(value):
            for kind in ("Column", "Measure"):
                if kind in node and isinstance(node[kind], dict):
                    field = node[kind]
                    entity = field.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    if entity and field.get("Property") not in tables.get(entity, {}).get(kind, set()):
                        issues["invalid_" + kind.lower() + "_binding"] += 1
            resource = node.get("ResourcePackageItem")
            if isinstance(resource, dict):
                key = (resource.get("PackageName"), resource.get("ItemName"))
                if key not in resources:
                    issues["unregistered_resource_reference"] += 1
    return {"status": "FAIL" if issues else "PASS", "scope": "static_project_dependencies",
            "project_name": project_path.name, "tables": len(tables),
            "measures": sum(len(table["Measure"]) for table in tables.values()),
            "pages": len(pages.get("pageOrder", [])), "visual_containers": visuals,
            "registered_resources": len(resources), "issues": dict(issues),
            "desktop_refresh_tested": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT / "dashboard/premium_growth.pbip")
    args = parser.parse_args()
    result = validate_dashboard(args.project)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
