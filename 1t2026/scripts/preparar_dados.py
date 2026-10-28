#!/usr/bin/env python3
"""Baixa, valida e extrai os BUs do primeiro turno de 2026."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from zipfile import ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
ZIP_DIR = PROJECT_ROOT / "01_origem_zip"
CSV_DIR = PROJECT_ROOT / "02_dados_csv"
DOC_DIR = PROJECT_ROOT / "03_documentacao"
AUDIT_DIR = PROJECT_ROOT / "auditoria"


def load_shared_module():
    path = REPOSITORY_ROOT / "2t2022" / "04_bi" / "scripts" / "prepare_sources.py"
    spec = importlib.util.spec_from_file_location("shared_tse_sources", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar as rotinas compartilhadas: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    shared = load_shared_module()
    for directory in (ZIP_DIR, CSV_DIR, DOC_DIR, AUDIT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    print("Consultando recursos oficiais do TSE para o primeiro turno de 2026...", flush=True)
    resources = shared.discover_resources(2026, 1)
    manifest: list[dict] = []
    documentation_hash: str | None = None

    for uf in sorted(resources):
        item = resources[uf]
        zip_path = ZIP_DIR / item["zip_name"]
        hash_path = ZIP_DIR / f"{item['zip_name']}.sha512"
        print(f"[{uf}] {zip_path.name}", flush=True)
        shared.fetch_small_file(item["hash_url"], hash_path)
        expected, expected_name = shared.expected_hash(hash_path)
        if expected_name != zip_path.name:
            raise RuntimeError(f"O SHA-512 de {uf} referencia {expected_name}, não {zip_path.name}")
        status = shared.download_validated(item["zip_url"], zip_path, expected)

        with ZipFile(zip_path) as archive:
            files = [member for member in archive.infolist() if not member.is_dir()]
            csv_members = [member for member in files if member.filename.lower().endswith(".csv")]
            pdf_members = [member for member in files if member.filename.lower().endswith(".pdf")]
            if len(files) != 2 or len(csv_members) != 1 or len(pdf_members) != 1:
                raise RuntimeError(f"Conteúdo inesperado em {zip_path.name}")
            csv_member = csv_members[0]
            csv_path = CSV_DIR / Path(csv_member.filename).name
            csv_status = shared.extract_member(archive, csv_member, csv_path)
            pdf_bytes = archive.read(pdf_members[0])
            current_documentation_hash = hashlib.sha256(pdf_bytes).hexdigest()
            if documentation_hash is None:
                documentation_hash = current_documentation_hash
                pdf_path = DOC_DIR / "leiame-boletimurnaweb.pdf"
                if (
                    not pdf_path.exists()
                    or hashlib.sha256(pdf_path.read_bytes()).hexdigest() != documentation_hash
                ):
                    temporary = pdf_path.with_name(pdf_path.name + ".part")
                    temporary.write_bytes(pdf_bytes)
                    temporary.replace(pdf_path)
            elif current_documentation_hash != documentation_hash:
                raise RuntimeError(f"Documentação divergente no ZIP de {uf}")

        print(f"    ZIP {status}; CSV {csv_status}; SHA-512 OK", flush=True)
        manifest.append({
            "uf": uf,
            "zip": zip_path.name,
            "zip_url": item["zip_url"],
            "hash_url": item["hash_url"],
            "sha512": expected,
            "tamanho_zip_bytes": zip_path.stat().st_size,
            "csv": csv_path.name,
            "tamanho_csv_bytes": csv_path.stat().st_size,
            "sha256_csv": shared.digest(csv_path, "sha256"),
        })

    write_json_atomic(AUDIT_DIR / "manifesto_downloads.json", {
        "ano": 2026,
        "turno": 1,
        "api": shared.API_URL.format(ano=2026),
        "quantidade_ufs": len(manifest),
        "sha256_documentacao": documentation_hash,
        "recursos": manifest,
    })
    print("Preparação concluída: 28 ZIPs validados e CSVs extraídos.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
