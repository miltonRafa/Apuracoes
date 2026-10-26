#!/usr/bin/env python3
"""Descobre, baixa, valida e extrai os boletins de urna publicados pelo TSE."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


DATA_ROOT = Path(__file__).resolve().parents[2]
ZIP_DIR = DATA_ROOT / "01_origem_zip"
CSV_DIR = DATA_ROOT / "02_dados_csv"
DOC_DIR = DATA_ROOT / "03_documentacao"
AUDIT_DIR = DATA_ROOT / "04_bi" / "auditoria"
API_URL = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{ano}-boletim-de-urna"
EXPECTED_UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
}
USER_AGENT = "apuracoes-pipeline/1.0 (+https://github.com/miltonRafa/Apuracoes)"


def request(url: str, *, range_start: int | None = None, timeout: int = 60):
    headers = {"User-Agent": USER_AGENT}
    if range_start:
        headers["Range"] = f"bytes={range_start}-"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def fetch_json(url: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with request(url) as response:
                return json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Falha ao consultar a API do TSE: {last_error}")


def fetch_small_file(url: str, destination: Path) -> None:
    temporary = destination.with_name(destination.name + ".part")
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with request(url) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
            return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Falha ao baixar {url}: {last_error}")


def download_with_resume(url: str, destination: Path) -> None:
    temporary = destination.with_name(destination.name + ".part")
    start = temporary.stat().st_size if temporary.exists() else 0
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            with request(url, range_start=start or None) as response:
                partial_response = getattr(response, "status", None) == 206
                mode = "ab" if start and partial_response else "wb"
                if mode == "wb":
                    start = 0
                content_length = int(response.headers.get("Content-Length", "0"))
                expected_total = start + content_length if content_length else 0
                copied = start
                next_report = 10
                with temporary.open(mode) as output:
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        copied += len(chunk)
                        if expected_total:
                            percentage = int(copied * 100 / expected_total)
                            if percentage >= next_report:
                                print(f"    {destination.name}: {percentage}%", flush=True)
                                next_report = min(100, percentage + 10)
                if expected_total and copied != expected_total:
                    raise IOError(f"download incompleto: {copied} de {expected_total} bytes")
            temporary.replace(destination)
            return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            start = temporary.stat().st_size if temporary.exists() else 0
            if attempt < 2:
                print(f"    nova tentativa após erro: {exc}", flush=True)
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Falha ao baixar {url}: {last_error}")


def digest(path: Path, algorithm: str = "sha512") -> str:
    checksum = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def expected_hash(path: Path) -> tuple[str, str]:
    parts = path.read_text(encoding="ascii").strip().split()
    if len(parts) < 2 or not re.fullmatch(r"[0-9a-fA-F]{128}", parts[0]):
        raise RuntimeError(f"Arquivo SHA-512 inválido: {path}")
    return parts[0].lower(), Path(parts[-1]).name


def crc32_file(path: Path) -> int:
    value = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value = zlib.crc32(chunk, value)
    return value & 0xFFFFFFFF


def extract_member(archive: ZipFile, member, destination: Path) -> str:
    if destination.exists() and destination.stat().st_size == member.file_size:
        if crc32_file(destination) == member.CRC:
            return "já extraído e validado"

    temporary = destination.with_name(destination.name + ".part")
    checksum = 0
    written = 0
    with archive.open(member) as source, temporary.open("wb") as output:
        while True:
            chunk = source.read(8 * 1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            checksum = zlib.crc32(chunk, checksum)
            written += len(chunk)
    if written != member.file_size or (checksum & 0xFFFFFFFF) != member.CRC:
        raise RuntimeError(f"Falha de CRC ao extrair {member.filename}")
    temporary.replace(destination)
    return "extraído"


def discover_resources(year: int, turn: int) -> dict[str, dict[str, str]]:
    api = API_URL.format(ano=year)
    payload = fetch_json(api)
    if not payload.get("success"):
        raise RuntimeError(f"A API do TSE não retornou sucesso para {year}")

    pattern = re.compile(rf"^(bweb_{turn}t_([A-Z]{{2}})_\d{{12}}\.zip)(\.sha512)?$")
    resources: dict[str, dict[str, str]] = {}
    for resource in payload["result"].get("resources", []):
        url = resource.get("url", "")
        filename = Path(urllib.parse.urlparse(url).path).name
        match = pattern.fullmatch(filename)
        if not match:
            continue
        zip_name, uf, hash_suffix = match.groups()
        item = resources.setdefault(uf, {"zip_name": zip_name})
        item["hash_url" if hash_suffix else "zip_url"] = url

    found = set(resources)
    if found != EXPECTED_UFS:
        missing = ", ".join(sorted(EXPECTED_UFS - found)) or "nenhuma"
        extra = ", ".join(sorted(found - EXPECTED_UFS)) or "nenhuma"
        raise RuntimeError(
            f"Publicação incompleta ou inesperada para {year}/{turn}º turno. "
            f"UFs ausentes: {missing}; extras: {extra}."
        )
    incomplete = [uf for uf, item in resources.items() if "zip_url" not in item or "hash_url" not in item]
    if incomplete:
        raise RuntimeError(f"ZIP ou hash ausente para: {', '.join(sorted(incomplete))}")
    return resources


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara os arquivos oficiais de boletim de urna.")
    parser.add_argument("--ano", type=int, default=2022)
    parser.add_argument("--turno", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()

    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Consultando recursos do TSE para {args.ano}, {args.turno}º turno...", flush=True)
    resources = discover_resources(args.ano, args.turno)
    manifest: list[dict] = []
    readme_hash: str | None = None

    for uf in sorted(resources):
        item = resources[uf]
        zip_path = ZIP_DIR / item["zip_name"]
        hash_path = ZIP_DIR / f"{item['zip_name']}.sha512"
        print(f"[{uf}] Preparando {zip_path.name}", flush=True)

        fetch_small_file(item["hash_url"], hash_path)
        expected, expected_name = expected_hash(hash_path)
        if expected_name != zip_path.name:
            raise RuntimeError(f"O hash de {uf} referencia {expected_name}, não {zip_path.name}")

        zip_status = "já baixado e validado"
        if not zip_path.exists() or digest(zip_path) != expected:
            print(f"    baixando {item['zip_url']}", flush=True)
            download_with_resume(item["zip_url"], zip_path)
            zip_status = "baixado"
        actual = digest(zip_path)
        if actual != expected:
            raise RuntimeError(f"SHA-512 divergente para {zip_path.name}")

        with ZipFile(zip_path) as archive:
            csv_members = [m for m in archive.infolist() if m.filename.lower().endswith(".csv")]
            pdf_members = [m for m in archive.infolist() if m.filename.lower().endswith(".pdf")]
            if len(csv_members) != 1 or len(pdf_members) != 1:
                raise RuntimeError(f"Conteúdo inesperado em {zip_path.name}")
            csv_member = csv_members[0]
            csv_status = extract_member(archive, csv_member, CSV_DIR / Path(csv_member.filename).name)

            pdf_bytes = archive.read(pdf_members[0])
            current_readme_hash = hashlib.sha256(pdf_bytes).hexdigest()
            if readme_hash is None:
                readme_hash = current_readme_hash
                readme_path = DOC_DIR / "leiame-boletimurnaweb.pdf"
                if not readme_path.exists() or hashlib.sha256(readme_path.read_bytes()).hexdigest() != readme_hash:
                    temporary = readme_path.with_name(readme_path.name + ".part")
                    temporary.write_bytes(pdf_bytes)
                    temporary.replace(readme_path)
            elif current_readme_hash != readme_hash:
                raise RuntimeError(f"Documentação divergente no ZIP de {uf}")

        print(f"    ZIP {zip_status}; CSV {csv_status}; SHA-512 OK", flush=True)
        manifest.append(
            {
                "uf": uf,
                "zip": zip_path.name,
                "zip_url": item["zip_url"],
                "hash_url": item["hash_url"],
                "sha512": actual,
                "tamanho_zip_bytes": zip_path.stat().st_size,
                "tamanho_csv_bytes": csv_member.file_size,
                "status_zip": zip_status,
                "status_csv": csv_status,
            }
        )

    report = {
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "ano": args.ano,
        "turno": args.turno,
        "api": API_URL.format(ano=args.ano),
        "quantidade_ufs": len(manifest),
        "recursos": manifest,
    }
    (AUDIT_DIR / "manifesto_downloads.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Fontes preparadas: {len(manifest)} ZIPs e CSVs validados.", flush=True)


if __name__ == "__main__":
    main()
