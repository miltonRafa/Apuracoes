#!/usr/bin/env python3
"""Regressões dos casos de borda encontrados na revisão do projeto."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from zipfile import ZipFile


REPOSITORY = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível importar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_2022 = load_module(
    "prepare_2022", REPOSITORY / "2t2022" / "04_bi" / "scripts" / "prepare_sources.py"
)
download_2026 = load_module(
    "download_2026", REPOSITORY / "2t2026" / "scripts" / "baixar_dados.py"
)


class PrepareSources2022Tests(unittest.TestCase):
    def test_rejects_two_complete_versions_for_same_uf(self):
        payload = {"success": True, "result": {"resources": []}}
        for timestamp in ("301020221900", "311020221535"):
            name = f"bweb_2t_AC_{timestamp}.zip"
            payload["result"]["resources"].extend([
                {"url": f"https://cdn.tse.jus.br/estatistica/sead/odsele/{name}"},
                {"url": f"https://cdn.tse.jus.br/estatistica/sead/odsele/{name}.sha512"},
            ])
        original = prepare_2022.fetch_json
        prepare_2022.fetch_json = lambda _url: payload
        try:
            with self.assertRaisesRegex(RuntimeError, "Mais de um par"):
                prepare_2022.discover_resources(2022, 2)
        finally:
            prepare_2022.fetch_json = original

    def test_http_416_promotes_complete_partial_file_for_hash_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "arquivo.zip"
            partial = destination.with_name(destination.name + ".part")
            partial.write_bytes(b"arquivo completo")
            original = prepare_2022.request

            def range_not_satisfiable(url, **_kwargs):
                raise urllib.error.HTTPError(url, 416, "Range Not Satisfiable", None, None)

            prepare_2022.request = range_not_satisfiable
            try:
                prepare_2022.download_with_resume("https://cdn.tse.jus.br/arquivo.zip", destination)
            finally:
                prepare_2022.request = original
            self.assertEqual(destination.read_bytes(), b"arquivo completo")
            self.assertFalse(partial.exists())

    def test_same_size_corruption_is_reextracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "fonte.zip"
            destination = root / "dado.csv"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("dado.csv", b"conteudo correto")
            destination.write_bytes(b"x" * len(b"conteudo correto"))
            with ZipFile(archive_path) as archive:
                member = archive.getinfo("dado.csv")
                status = prepare_2022.extract_member(archive, member, destination)
            self.assertEqual(status, "extraído")
            self.assertEqual(destination.read_bytes(), b"conteudo correto")


class Downloader2026Tests(unittest.TestCase):
    def test_config_cannot_reduce_expected_ufs(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps({
                "ano": 2026,
                "turno": 2,
                "api_url": "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=x",
                "ufs_esperadas": ["SP"],
            }), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exatamente as 27 UFs"):
                download_2026.load_config(config_path)

    def test_catalog_rejects_non_official_download_host(self):
        payload = {"success": True, "result": {"resources": [
            {"url": "https://example.org/bweb_2t_SP_261020261200.zip"},
        ]}}
        with self.assertRaisesRegex(RuntimeError, "URL inesperada"):
            download_2026.discover_resources(payload, 2)


if __name__ == "__main__":
    unittest.main()
