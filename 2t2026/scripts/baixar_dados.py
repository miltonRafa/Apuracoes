#!/usr/bin/env python3
"""Descobre e baixa os ZIPs do segundo turno de 2026 sem extrair os dados."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DOWNLOAD_DIR = PROJECT_ROOT / "01_origem_zip"
AUDIT_DIR = PROJECT_ROOT / "auditoria"
USER_AGENT = "apuracoes-pipeline/1.0 (+https://github.com/miltonRafa/Apuracoes)"
EXPECTED_UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
}


def request(url: str, *, range_start: int | None = None, timeout: int = 60):
    headers = {"User-Agent": USER_AGENT}
    if range_start:
        headers["Range"] = f"bytes={range_start}-"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def load_config(path: Path) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Configuração não encontrada: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON inválido em {path}: {exc}") from exc

    required = {"ano", "turno", "api_url", "ufs_esperadas"}
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError(f"Campos ausentes em {path}: {', '.join(missing)}")
    if config["ano"] != 2026 or config["turno"] != 2:
        raise RuntimeError("Este pré-projeto aceita somente o segundo turno de 2026.")
    if not isinstance(config["api_url"], str) or not config["api_url"].startswith("https://"):
        raise RuntimeError("api_url deve ser um endereço HTTPS.")
    if not isinstance(config["ufs_esperadas"], list) or not config["ufs_esperadas"]:
        raise RuntimeError("ufs_esperadas deve ser uma lista não vazia.")

    ufs = config["ufs_esperadas"]
    if len(ufs) != len(set(ufs)) or any(not re.fullmatch(r"[A-Z]{2}", uf) for uf in ufs):
        raise RuntimeError("ufs_esperadas contém siglas inválidas ou repetidas.")
    if set(ufs) != EXPECTED_UFS:
        raise RuntimeError(
            "ufs_esperadas deve conter exatamente as 27 UFs e Exterior (ZZ). "
            f"Ausentes: {sorted(EXPECTED_UFS - set(ufs))}; extras: {sorted(set(ufs) - EXPECTED_UFS)}."
        )
    return config


def fetch_json(url: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with request(url) as response:
                return json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(
        "Não foi possível consultar a publicação do TSE. "
        "Ela pode ainda não existir ou o endereço em config.json pode ter mudado. "
        f"Detalhe: {last_error}"
    )


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
                time.sleep(2**attempt)
    raise RuntimeError(f"Falha ao baixar {url}: {last_error}")


def download_to_partial(url: str, destination: Path) -> Path:
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
                next_report = ((int(copied * 100 / expected_total) // 10) + 1) * 10 if expected_total else 10

                with temporary.open(mode) as output:
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        copied += len(chunk)
                        if expected_total and int(copied * 100 / expected_total) >= next_report:
                            print(f"    {destination.name}: {min(100, int(copied * 100 / expected_total))}%", flush=True)
                            next_report += 10

                if expected_total and copied != expected_total:
                    raise IOError(f"download incompleto: {copied} de {expected_total} bytes")
            return temporary
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 416 and temporary.exists():
                return temporary
            if attempt < 2:
                print(f"    nova tentativa após erro HTTP: {exc}", flush=True)
                time.sleep(2**attempt)
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 2:
                print(f"    nova tentativa após erro: {exc}", flush=True)
                time.sleep(2**attempt)

    raise RuntimeError(f"Falha ao baixar {url}: {last_error}")


def digest(path: Path) -> str:
    checksum = hashlib.sha512()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def read_expected_hash(path: Path) -> tuple[str, str]:
    parts = path.read_text(encoding="ascii").strip().split()
    if len(parts) < 2 or not re.fullmatch(r"[0-9a-fA-F]{128}", parts[0]):
        raise RuntimeError(f"Arquivo SHA-512 inválido: {path}")
    return parts[0].lower(), Path(parts[-1]).name


def discover_resources(payload: dict, turn: int) -> tuple[dict[str, dict[str, str]], list[str]]:
    if not payload.get("success") or not isinstance(payload.get("result"), dict):
        raise RuntimeError("A API do TSE não retornou uma publicação válida.")

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
    for uf, items in by_uf.items():
        resources[uf] = items[0]
    return resources, sorted(incomplete)


def download_validated(url: str, destination: Path, expected: str) -> str:
    if destination.exists() and digest(destination) == expected:
        return "já baixado e validado"

    for checksum_attempt in range(2):
        temporary = download_to_partial(url, destination)
        actual = digest(temporary)
        if actual == expected:
            temporary.replace(destination)
            return "baixado e validado"
        temporary.unlink(missing_ok=True)
        if checksum_attempt == 0:
            print("    SHA-512 divergente; repetindo o download do início", flush=True)
    raise RuntimeError(f"SHA-512 divergente após duas tentativas: {destination.name}")


def write_manifest(report: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    destination = AUDIT_DIR / "manifesto_downloads.json"
    temporary = destination.with_name(destination.name + ".part")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa os ZIPs oficiais do 2º turno de 2026.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--permitir-parcial",
        action="store_true",
        help="baixa os pares já publicados mesmo que ainda faltem UFs",
    )
    args = parser.parse_args()

    config = load_config(args.config.resolve())
    expected_ufs = set(config["ufs_esperadas"])
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    print("Consultando a publicação oficial do TSE para o 2º turno de 2026...", flush=True)
    payload = fetch_json(config["api_url"])
    resources, incomplete_pairs = discover_resources(payload, config["turno"])
    found_ufs = set(resources)
    missing_ufs = sorted(expected_ufs - found_ufs)
    extra_ufs = sorted(found_ufs - expected_ufs)

    if extra_ufs:
        raise RuntimeError(f"Abrangências inesperadas na publicação: {', '.join(extra_ufs)}")
    if (missing_ufs or incomplete_pairs) and not args.permitir_parcial:
        details = []
        if missing_ufs:
            details.append(f"UFs ausentes: {', '.join(missing_ufs)}")
        if incomplete_pairs:
            details.append(f"pares incompletos: {', '.join(incomplete_pairs)}")
        raise RuntimeError(
            "A publicação ainda está incompleta. Nenhum ZIP foi baixado. "
            + "; ".join(details)
            + ". Use --permitir-parcial somente se quiser antecipar os arquivos disponíveis."
        )
    if not resources:
        raise RuntimeError("Nenhum par ZIP/SHA-512 do segundo turno foi encontrado.")

    manifest: list[dict] = []
    for uf in sorted(resources):
        item = resources[uf]
        zip_path = DOWNLOAD_DIR / item["zip_name"]
        hash_path = DOWNLOAD_DIR / f"{item['zip_name']}.sha512"
        print(f"[{uf}] {zip_path.name}", flush=True)

        fetch_small_file(item["hash_url"], hash_path)
        expected_hash, expected_name = read_expected_hash(hash_path)
        if expected_name != zip_path.name:
            raise RuntimeError(f"O SHA-512 de {uf} referencia {expected_name}, não {zip_path.name}")

        status = download_validated(item["zip_url"], zip_path, expected_hash)
        print(f"    {status}; SHA-512 OK", flush=True)
        manifest.append(
            {
                "uf": uf,
                "zip": zip_path.name,
                "zip_url": item["zip_url"],
                "hash_url": item["hash_url"],
                "sha512": expected_hash,
                "tamanho_bytes": zip_path.stat().st_size,
            }
        )

    complete = not missing_ufs and not incomplete_pairs
    report = {
        "status": "COMPLETO" if complete else "PARCIAL",
        "ano": config["ano"],
        "turno": config["turno"],
        "api": config["api_url"],
        "quantidade_baixada": len(manifest),
        "ufs_ausentes": missing_ufs,
        "pares_incompletos": incomplete_pairs,
        "recursos": manifest,
    }
    write_manifest(report)
    print(f"Download concluído: {len(manifest)} ZIPs íntegros; status {report['status']}.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
