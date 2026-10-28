#!/usr/bin/env python3
"""Gera ou verifica o manifesto criptográfico das saídas reproduzíveis."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BI_ROOT = ROOT / "04_bi"
AUDIT_DIR = BI_ROOT / "auditoria"
CHART_DIR = BI_ROOT / "graficos"
MANIFEST = AUDIT_DIR / "manifesto_saidas.csv"
GENERATED_CHARTS = (
    "correlacao_defasagem.svg",
    "distribuicao_intervalos.svg",
    "evolucao_percentual_blocos.svg",
)
GENERATED_AUDIT_FILES = (
    "RELATORIO_VALIDACAO.md",
    "alertas_temporais.csv",
    "blocos_totalizacao.csv",
    "comparacao_por_uf.csv",
    "manifesto_downloads.json",
    "manifesto_fontes.csv",
    "metadados_execucao.json",
    "resultado_validacao.csv",
    "resultado_validacao.json",
)


def sha256(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def expected_outputs() -> list[Path]:
    paths = [path for path in (BI_ROOT / "dados").rglob("*") if path.is_file()]
    paths.extend(path for path in (BI_ROOT / "notebooks").glob("*.ipynb") if path.is_file())
    paths.extend(CHART_DIR / name for name in GENERATED_CHARTS)
    paths.extend(AUDIT_DIR / name for name in GENERATED_AUDIT_FILES)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError("Saídas obrigatórias ausentes: " + ", ".join(str(path) for path in missing))
    return sorted(set(paths), key=lambda path: path.relative_to(ROOT).as_posix())


def generate() -> None:
    rows = []
    for path in expected_outputs():
        rows.append((path.relative_to(ROOT).as_posix(), path.stat().st_size, sha256(path)))
    temporary = MANIFEST.with_name(MANIFEST.name + ".part")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter=";", lineterminator="\n")
        writer.writerow(["arquivo", "tamanho_bytes", "sha256"])
        writer.writerows(rows)
    temporary.replace(MANIFEST)
    print(f"Manifesto de saídas gerado: {len(rows)} arquivos.")


def verify() -> None:
    if not MANIFEST.is_file():
        raise RuntimeError(f"Manifesto ausente: {MANIFEST}")
    with MANIFEST.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream, delimiter=";"))
    problems: list[str] = []
    recorded = set()
    for record in records:
        relative = record["arquivo"]
        recorded.add(relative)
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"ausente: {relative}")
            continue
        if path.stat().st_size != int(record["tamanho_bytes"]):
            problems.append(f"tamanho divergente: {relative}")
            continue
        if sha256(path) != record["sha256"]:
            problems.append(f"SHA-256 divergente: {relative}")
    current = {path.relative_to(ROOT).as_posix() for path in expected_outputs()}
    for relative in sorted(current - recorded):
        problems.append(f"saída não registrada: {relative}")
    if problems:
        raise RuntimeError("Manifesto de saídas reprovado:\n- " + "\n- ".join(problems))
    print(f"Manifesto de saídas verificado: {len(records)} arquivos íntegros.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--gerar", action="store_true")
    mode.add_argument("--verificar", action="store_true")
    args = parser.parse_args()
    if args.gerar:
        generate()
    else:
        verify()


if __name__ == "__main__":
    main()
