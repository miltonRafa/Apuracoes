#!/usr/bin/env python3
"""Consultas rápidas para revisar a camada analítica gerada."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
BI = ROOT / "04_bi" / "dados"


def print_table(columns, rows) -> None:
    widths = [len(str(c)) for c in columns]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))
    print(" | ".join(str(c).ljust(widths[i]) for i, c in enumerate(columns)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta a camada BI validada.")
    parser.add_argument("consulta", choices=["resumo", "cargos", "periodo", "apuracao"])
    parser.add_argument("--uf", help="Filtra a UF na consulta de apuração (ex.: SP).")
    parser.add_argument("--cargo", type=int, default=1, help="Código do cargo; 1=Presidente, 3=Governador.")
    parser.add_argument("--limite", type=int, default=20)
    args = parser.parse_args()

    con = duckdb.connect()
    votes = str((BI / "fato_votos" / "**" / "*.parquet").resolve()).replace("'", "''")
    ballots = str((BI / "fato_boletins" / "**" / "*.parquet").resolve()).replace("'", "''")
    votable = str((BI / "dimensoes" / "dim_votavel.parquet").resolve()).replace("'", "''")
    con.execute(f"CREATE VIEW votos AS SELECT * FROM read_parquet('{votes}', hive_partitioning=true)")
    con.execute(f"CREATE VIEW boletins AS SELECT * FROM read_parquet('{ballots}', hive_partitioning=true)")
    con.execute(f"CREATE VIEW votaveis AS SELECT * FROM read_parquet('{votable}')")

    if args.consulta == "resumo":
        query = """
            SELECT count(*) AS registros_votos, sum(qt_votos) AS votos,
                   count(DISTINCT id_bu_cargo) AS boletins, count(DISTINCT sg_uf) AS ufs
            FROM votos
        """
        params = []
    elif args.consulta == "cargos":
        query = """
            SELECT b.cd_cargo, count(*) AS boletins, sum(b.qt_comparecimento) AS votos,
                   min(b.dt_bu_recebido) AS primeiro_recebimento,
                   max(b.dt_bu_recebido) AS ultimo_recebimento
            FROM boletins b GROUP BY b.cd_cargo ORDER BY b.cd_cargo
        """
        params = []
    elif args.consulta == "periodo":
        query = """
            SELECT cd_cargo, sg_uf, min(dt_bu_recebido) AS primeiro,
                   max(dt_bu_recebido) AS ultimo, count(*) AS boletins
            FROM boletins GROUP BY cd_cargo, sg_uf ORDER BY cd_cargo, sg_uf
        """
        params = []
    else:
        uf_filter = "AND v.sg_uf = ?" if args.uf else ""
        query = f"""
            SELECT v.dt_bu_recebido, v.sg_uf, d.nm_votavel, sum(v.qt_votos) AS votos_no_lote
            FROM votos v JOIN votaveis d USING (id_votavel)
            WHERE v.cd_cargo = ? {uf_filter}
            GROUP BY v.dt_bu_recebido, v.sg_uf, d.nm_votavel
            ORDER BY v.dt_bu_recebido, v.sg_uf, d.nm_votavel
            LIMIT ?
        """
        params = [args.cargo] + ([args.uf.upper()] if args.uf else []) + [args.limite]
    result = con.execute(query, params)
    print_table([item[0] for item in result.description], result.fetchall())
    con.close()


if __name__ == "__main__":
    main()
