"""Alta docente explícita de repositorio PRIVADO de un grupo, sin tocar maestro.

No crea repositorios remotos. Requiere que el docente haya creado uno vacío y
privado en GitHub; separa commit inicial local de envío remoto autorizado.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from lab01_common_v2 import _config, _read_json, _write_json


def run(command: list[str], root: Path) -> str:
    r = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"{' '.join(command[:3])}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def repo_slug(url: str) -> str:
    """Acepta solo HTTPS sin credenciales o SSH GitHub; prohíbe el maestro."""
    value = url.strip()
    m = re.fullmatch(r"https://github\.com/([\w-]+)/([\w.-]+?)(?:\.git)?/?", value)
    if not m:
        m = re.fullmatch(r"git@github\.com:([\w-]+)/([\w.-]+?)(?:\.git)?", value)
    if not m:
        raise ValueError("Se requiere URL HTTPS o SSH de un repositorio GitHub sin credenciales")
    owner, name = m.group(1), m.group(2)
    if name.lower().removesuffix(".git") == "gestion_empresas_mineras_repo":
        raise ValueError("No se permite utilizar el repositorio maestro docente")
    return f"{owner}/{name}" 


def private_remote(root: Path, url: str) -> str:
    slug = repo_slug(url)
    run(["gh", "auth", "status"], root)
    info = json.loads(run(["gh", "repo", "view", slug, "--json", "visibility"], root))
    if info.get("visibility") != "PRIVATE":
        raise ValueError("El repositorio remoto NO está confirmado como privado")
    return slug


def configure(root: Path, url: str, branch: str, confirmed: bool) -> dict:
    if not confirmed:
        raise PermissionError("Falta --confirmar-docente")
    config = _config(root)
    slug = private_remote(root, url)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,39}", branch):
        raise ValueError("Nombre de rama no admitido")
    if (root / ".git").exists():
        raise FileExistsError("La carpeta ya tiene Git. No se reinicializa ni se sobreescribe su historia")
    heads = run(["git", "ls-remote", "--heads", url], root)
    if heads:
        raise ValueError("El remoto NO está vacío; clonar primero y trasladar el kit tras revisar diferencias")
    if config.get("repo_url") or config.get("rama_base"):
        raise ValueError("grupo.json ya tiene un destino; revisar sin reemplazar")
    config.update(repo_url=url, rama_base=branch)
    # Preflight: las fuentes del kit deben existir antes de crear historia.
    for path in ("visor", "plantilla", ".github/agents/kai-gestion.agent.md", ".gitignore"):
        if not (root / path).exists():
            raise FileNotFoundError(f"Kit grupal incompleto: {path}")
    _write_json(root / "grupo.json", config)
    run(["git", "init", "-b", branch], root)
    run(["git", "remote", "add", "origin", url], root)
    paths = [".github", ".gitignore", "grupo.json", "visor", "plantilla", "scripts",
             "LEEME_ESTUDIANTE.md", "LEEME_REPRESENTANTE.md", "PREGUNTAS_LAB01_V2.md",
             "INICIAR_LAB01_V2.cmd", "EXPORTAR_MI_TRABAJO.cmd", "CIERRE_GRUPAL.cmd"]
    existing = [x for x in paths if (root / x).exists()]
    run(["git", "add", "--", *existing], root)
    staged = run(["git", "diff", "--cached", "--name-only"], root).splitlines()
    if any(x.startswith(("trabajos/", "cierre/", ".idea/", ".venv/")) for x in staged):
        raise ValueError("No se permite versionar sesiones privadas ni carpetas de IDE")
    run(["git", "commit", "-m", f"Base inicial privada Lab01 {config['grupo']} {config['fecha_laboratorio']}"], root)
    return {"grupo": config["grupo"], "repositorio": slug, "rama": branch,
            "commit_inicial": run(["git", "rev-parse", "HEAD"], root),
            "estado": "BASE_LOCAL_INICIALIZADA; NO PUSH"}


def publish(root: Path, confirmed: bool) -> dict:
    if not confirmed:
        raise PermissionError("Falta --autorizar-docente; ningún push ejecutado")
    config = _config(root)
    url, branch = config.get("repo_url"), config.get("rama_base")
    if not url or not branch:
        raise ValueError("El grupo aún no está configurado")
    slug = private_remote(root, url)
    if run(["git", "remote", "get-url", "origin"], root).rstrip("/").removesuffix(".git") != url.rstrip("/").removesuffix(".git"):
        raise ValueError("Origin difiere del repositorio autorizado")
    if run(["git", "branch", "--show-current"], root) != branch:
        raise ValueError("Rama local distinta de la rama autorizada")
    if run(["git", "status", "--porcelain"], root):
        raise ValueError("Existen cambios locales pendientes; primero revisar")
    if run(["git", "ls-remote", "--heads", url], root):
        raise ValueError("El remoto tiene historial; no publicar encima sin revisión manual")
    sha = run(["git", "rev-parse", "HEAD"], root)
    run(["git", "push", "-u", "origin", branch], root)
    remote = run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], root).split()
    if not remote or remote[0] != sha:
        raise RuntimeError("El SHA remoto no coincide con la base local")
    return {"grupo": config["grupo"], "repositorio": slug, "rama": branch,
            "sha": sha, "estado": "BASE_REMOTA_VERIFICADA"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preparación docente de repositorios privados Lab 01")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest="accion", required=True)
    c = sub.add_parser("configurar")
    c.add_argument("--repo-url", required=True)
    c.add_argument("--rama", default="main")
    c.add_argument("--confirmar-docente", action="store_true")
    p = sub.add_parser("publicar-inicial")
    p.add_argument("--autorizar-docente", action="store_true")
    args = parser.parse_args()
    try:
        if args.accion == "configurar":
            result = configure(args.raiz.resolve(), args.repo_url, args.rama, args.confirmar_docente)
        else:
            result = publish(args.raiz.resolve(), args.autorizar_docente)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, FileExistsError, PermissionError, RuntimeError) as exc:
        print(f"REPO GRUPAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
