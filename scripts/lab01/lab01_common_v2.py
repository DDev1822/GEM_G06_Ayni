"""Utilidades de lectura y escritura breve del Laboratorio 01 v2."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET


OPERATIONS = {
    "G01": "Qhapaq Copper", "G02": "Kallpa Copper", "G03": "Sumaq Copper",
    "G04": "Tikari Copper", "G05": "Wayra Copper", "G06": "Ayni Copper",
}
XML_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")
    temp.replace(path)
    if _read_json(path) != value:
        raise RuntimeError(f"No se confirmó la escritura de {path}")


def _config(root: Path) -> dict:
    config = _read_json(root / "grupo.json")
    group = config.get("grupo")
    if group not in OPERATIONS or config.get("operacion") != OPERATIONS[group]:
        raise ValueError("Identidad del grupo inválida en grupo.json")
    return config


def _alias(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,23}", value):
        raise ValueError("Alias de 2–24 caracteres: letras sin tildes, números, _ o -; empieza con letra")
    return value


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels.findall(f"{{{XML_PKG}}}Relationship")}
    paths = {}
    for item in workbook.findall(f".//{{{XML_MAIN}}}sheet"):
        target = targets[item.attrib[f"{{{XML_REL}}}id"]]
        paths[item.attrib["name"]] = target.lstrip("/") if target.startswith("/") else "xl/" + target
    return paths


def workbook_values(path: Path, wanted: dict[str, list[str]]) -> dict[str, dict[str, str]]:
    """Lee valores registrados y cachés de fórmulas; no calcula ni edita."""
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("XLSX dañado")
        paths = _sheet_paths(archive)
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in item.iter(f"{{{XML_MAIN}}}t"))
                      for item in root.findall(f"{{{XML_MAIN}}}si")]
        result = {}
        for sheet, addresses in wanted.items():
            if sheet not in paths:
                raise ValueError(f"Falta la hoja {sheet}")
            document = ET.fromstring(archive.read(paths[sheet]))
            cells = {cell.attrib["r"]: cell for cell in document.iter(f"{{{XML_MAIN}}}c")}
            result[sheet] = {}
            for address in addresses:
                cell = cells.get(address)
                value = ""
                if cell is not None:
                    raw = cell.find(f"{{{XML_MAIN}}}v")
                    inline = cell.find(f"{{{XML_MAIN}}}is")
                    if raw is not None and raw.text is not None:
                        value = shared[int(raw.text)] if cell.attrib.get("t") == "s" else raw.text
                    elif inline is not None:
                        value = "".join(t.text or "" for t in inline.iter(f"{{{XML_MAIN}}}t"))
                result[sheet][address] = value.strip()
        return result
