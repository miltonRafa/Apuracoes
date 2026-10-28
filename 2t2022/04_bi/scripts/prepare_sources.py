#!/usr/bin/env python3
"""Descobre, baixa, valida e extrai as fontes de resultados publicadas pelo TSE."""

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
from pathlib import Path
from zipfile import ZipFile


DATA_ROOT = Path(__file__).resolve().parents[2]
ZIP_DIR = DATA_ROOT / "01_origem_zip"
CSV_DIR = DATA_ROOT / "02_dados_csv"
DOC_DIR = DATA_ROOT / "03_documentacao"
AUDIT_DIR = DATA_ROOT / "04_bi" / "auditoria"
HISTORY_DIR = DATA_ROOT / "04_bi" / "fontes" / "historico_totalizacao"
API_URL = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{ano}-boletim-de-urna"
RESOURCE_API_URL = "https://dadosabertos.tse.jus.br/api/3/action/resource_show?id={resource_id}"
HISTORY_RESOURCE_PAGE = (
    "https://dadosabertos.tse.jus.br/dataset/resultados-2022/resource/"
    "7cd53725-5dc5-4954-aee9-7dbf4097d26c"
)
HISTORY_RESOURCE_ID = "7cd53725-5dc5-4954-aee9-7dbf4097d26c"
HISTORY_PACKAGE_ID = "5db2c9ef-a63b-4c0c-a2ec-d08002f49897"
HISTORY_ZIP_NAME = "Historico_Totalizacao_Presidente_BR_2T_2022.zip"
HISTORY_ZIP_SHA256 = "1f12128fbcfacab755e0e83d9c0a350ed99ae68ea3d024aaa7bc58fe0c1dda3c"
HISTORY_MEMBERS_SHA256 = {
    "Historico_Totalizacao_Presidente_BR_2T_2022.csv": (
        "00013c958f13b2cf1a842c4398ca7cb52cf5ef46d26ce91f99c1a0ad8d0f663d"
    ),
    "leiame.pdf": "453cf754ad71b7bd9bcd31303fd14aefdecb7d091388ba585706ebd3c03d763f",
}
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
    last_error: Exception | None = None

    for attempt in range(3):
        start = temporary.stat().st_size if temporary.exists() else 0
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
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 416 and temporary.exists():
                # O arquivo parcial pode já estar completo. O chamador sempre
                # confere o hash forte antes de aceitá-lo.
                temporary.replace(destination)
                return
            if attempt < 2:
                print(f"    nova tentativa após erro HTTP: {exc}", flush=True)
                time.sleep(2 ** attempt)
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
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


def download_validated(
    url: str,
    destination: Path,
    expected: str,
    algorithm: str = "sha512",
) -> str:
    if destination.exists() and digest(destination, algorithm) == expected:
        return "já baixado e validado"

    for checksum_attempt in range(2):
        download_with_resume(url, destination)
        if digest(destination, algorithm) == expected:
            return "baixado e validado"
        destination.unlink(missing_ok=True)
        destination.with_name(destination.name + ".part").unlink(missing_ok=True)
        if checksum_attempt == 0:
            print("    hash divergente; repetindo o download do início", flush=True)
    raise RuntimeError(f"{algorithm.upper()} divergente após duas tentativas: {destination.name}")


def expected_hash(path: Path) -> tuple[str, str]:
    parts = path.read_text(encoding="ascii").strip().split()
    if len(parts) < 2 or not re.fullmatch(r"[0-9a-fA-F]{128}", parts[0]):
        raise RuntimeError(f"Arquivo SHA-512 inválido: {path}")
    return parts[0].lower(), Path(parts[-1]).name


def extract_member(archive: ZipFile, member, destination: Path) -> str:
    if destination.exists() and destination.stat().st_size == member.file_size:
        member_digest = hashlib.sha256()
        with archive.open(member) as source:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                member_digest.update(chunk)
        if digest(destination, "sha256") == member_digest.hexdigest():
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
    candidates: dict[tuple[str, str], dict[str, str]] = {}
    for resource in payload["result"].get("resources", []):
        url = resource.get("url", "")
        parsed = urllib.parse.urlparse(url)
        filename = Path(parsed.path).name
        match = pattern.fullmatch(filename)
        if not match:
            continue
        if parsed.scheme != "https" or parsed.hostname != "cdn.tse.jus.br":
            raise RuntimeError(f"URL inesperada no catálogo do TSE: {url}")
        zip_name, uf, hash_suffix = match.groups()
        item = candidates.setdefault((uf, zip_name), {"zip_name": zip_name})
        item["hash_url" if hash_suffix else "zip_url"] = url

    resources: dict[str, dict[str, str]] = {}
    incomplete: list[str] = []
    by_uf: dict[str, list[dict[str, str]]] = {}
    for (uf, zip_name), item in candidates.items():
        if "zip_url" not in item or "hash_url" not in item:
            incomplete.append(f"{uf}/{zip_name}")
            continue
        by_uf.setdefault(uf, []).append(item)

    ambiguous = sorted(uf for uf, items in by_uf.items() if len(items) > 1)
    if ambiguous:
        raise RuntimeError(f"Mais de um par ZIP/SHA-512 encontrado para: {', '.join(ambiguous)}")
    if incomplete:
        raise RuntimeError(f"Pares ZIP/SHA-512 incompletos: {', '.join(sorted(incomplete))}")
    for uf, items in by_uf.items():
        resources[uf] = items[0]

    found = set(resources)
    if found != EXPECTED_UFS:
        missing = ", ".join(sorted(EXPECTED_UFS - found)) or "nenhuma"
        extra = ", ".join(sorted(found - EXPECTED_UFS)) or "nenhuma"
        raise RuntimeError(
            f"Publicação incompleta ou inesperada para {year}/{turn}º turno. "
            f"UFs ausentes: {missing}; extras: {extra}."
        )
    return resources


def discover_history_resource() -> dict[str, str]:
    api = RESOURCE_API_URL.format(resource_id=HISTORY_RESOURCE_ID)
    payload = fetch_json(api)
    if not payload.get("success"):
        raise RuntimeError("A API do TSE não retornou sucesso para o histórico da totalização")

    resource = payload.get("result", {})
    checks = {
        "id": HISTORY_RESOURCE_ID,
        "package_id": HISTORY_PACKAGE_ID,
        "mimetype": "application/zip",
    }
    for field, expected in checks.items():
        if resource.get(field) != expected:
            raise RuntimeError(
                f"Metadado inesperado no histórico: {field}={resource.get(field)!r}; "
                f"esperado={expected!r}"
            )

    url = resource.get("url", "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "cdn.tse.jus.br":
        raise RuntimeError(f"URL inesperada para o histórico: {url}")
    if Path(parsed.path).name != HISTORY_ZIP_NAME:
        raise RuntimeError(f"Nome inesperado para o ZIP do histórico: {url}")

    return {
        "api_url": api,
        "resource_page": HISTORY_RESOURCE_PAGE,
        "resource_id": HISTORY_RESOURCE_ID,
        "name": resource.get("name", ""),
        "zip_url": url,
    }


def prepare_history_resource() -> dict[str, object]:
    resource = discover_history_resource()
    zip_path = ZIP_DIR / HISTORY_ZIP_NAME
    print(f"[HISTÓRICO] Preparando {zip_path.name}", flush=True)

    if not zip_path.exists() or digest(zip_path, "sha256") != HISTORY_ZIP_SHA256:
        print(f"    baixando {resource['zip_url']}", flush=True)
    zip_status = download_validated(
        resource["zip_url"], zip_path, HISTORY_ZIP_SHA256, "sha256"
    )

    actual_zip_hash = digest(zip_path, "sha256")
    if actual_zip_hash != HISTORY_ZIP_SHA256:
        raise RuntimeError(
            f"SHA-256 divergente para {zip_path.name}: "
            f"esperado {HISTORY_ZIP_SHA256}; obtido {actual_zip_hash}"
        )

    extracted: list[dict[str, str | int]] = []
    with ZipFile(zip_path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        names = {Path(member.filename).name for member in members}
        expected_names = set(HISTORY_MEMBERS_SHA256)
        if names != expected_names or len(members) != len(expected_names):
            raise RuntimeError(
                f"Conteúdo inesperado em {zip_path.name}: "
                f"esperado {sorted(expected_names)}; obtido {sorted(names)}"
            )

        for member in members:
            name = Path(member.filename).name
            destination = HISTORY_DIR / name
            status = extract_member(archive, member, destination)
            actual_member_hash = digest(destination, "sha256")
            expected_member_hash = HISTORY_MEMBERS_SHA256[name]
            if actual_member_hash != expected_member_hash:
                raise RuntimeError(
                    f"SHA-256 divergente para {name}: "
                    f"esperado {expected_member_hash}; obtido {actual_member_hash}"
                )
            extracted.append(
                {
                    "arquivo": name,
                    "tamanho_bytes": destination.stat().st_size,
                    "sha256": actual_member_hash,
                }
            )

    print(f"    ZIP {zip_status}; CSV/PDF validados por CRC e SHA-256", flush=True)
    return {
        **resource,
        "zip": zip_path.name,
        "zip_sha256": actual_zip_hash,
        "tamanho_zip_bytes": zip_path.stat().st_size,
        "arquivos_extraidos": extracted,
    }


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara os BUs e o histórico oficial da totalização."
    )
    parser.add_argument("--ano", type=int, default=2022)
    parser.add_argument("--turno", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    if args.ano != 2022 or args.turno != 2:
        parser.error("Este projeto aceita exclusivamente o segundo turno de 2022.")

    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

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

        if not zip_path.exists() or digest(zip_path) != expected:
            print(f"    baixando {item['zip_url']}", flush=True)
        zip_status = download_validated(item["zip_url"], zip_path, expected)
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
            }
        )

    history_manifest = None
    if args.ano == 2022 and args.turno == 2:
        history_manifest = prepare_history_resource()

    report = {
        "ano": args.ano,
        "turno": args.turno,
        "api": API_URL.format(ano=args.ano),
        "quantidade_ufs": len(manifest),
        "recursos": manifest,
        "historico_totalizacao": history_manifest,
    }
    write_json_atomic(AUDIT_DIR / "manifesto_downloads.json", report)
    history_message = " e histórico da totalização" if history_manifest else ""
    print(
        f"Fontes preparadas: {len(manifest)} ZIPs/CSVs{history_message} validados.",
        flush=True,
    )


if __name__ == "__main__":
    main()
