#!/usr/bin/env python3
"""Controles por seção: reconciliação do 2º turno e séries dos dois turnos."""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
DETAIL = ROOT / "04_bi/fontes/detalhe_votacao_secao/detalhe_votacao_secao_2022_BR.csv"
BWEB = ROOT / "02_dados_csv/bweb_2t_*.csv"
HISTORY = ROOT / "04_bi/fontes/historico_totalizacao/Historico_Totalizacao_Presidente_BR_2T_2022.csv"
AUDIT = ROOT / "04_bi/auditoria"


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=";", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET threads=4")
    connection.execute(
        f"""
        CREATE VIEW detalhe AS SELECT * FROM read_csv('{sql_path(DETAIL)}', delim=';', header=true, encoding='latin-1', all_varchar=true);
        CREATE VIEW bweb AS SELECT * FROM read_csv('{sql_path(BWEB)}', delim=';', header=true, encoding='latin-1', all_varchar=true);
        CREATE VIEW historico AS SELECT * FROM read_csv('{sql_path(HISTORY)}', delim=';', header=true, encoding='latin-1', all_varchar=true);
        """
    )
    total, exact = connection.execute(
        """
        WITH votos AS (
            SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO,
                   sum(CASE WHEN NR_VOTAVEL='13' THEN try_cast(QT_VOTOS AS BIGINT) ELSE 0 END) AS lula,
                   sum(CASE WHEN NR_VOTAVEL='22' THEN try_cast(QT_VOTOS AS BIGINT) ELSE 0 END) AS bolsonaro
            FROM bweb WHERE CD_ELEICAO='545' AND CD_CARGO_PERGUNTA='1' GROUP BY ALL
        ), secoes AS (
            SELECT try_strptime(d.DT_PRIM_TOT_PARCIAL_HOR_TSE, '%d/%m/%Y %H:%M:%S') AS instante,
                   count(*) AS secoes, sum(coalesce(v.lula, 0)) AS lula, sum(coalesce(v.bolsonaro, 0)) AS bolsonaro
            FROM detalhe AS d LEFT JOIN votos AS v USING (SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO)
            WHERE d.NR_TURNO='2' AND d.CD_ELEICAO='545' AND d.CD_CARGO='1' GROUP BY 1
        ), acumulado AS (
            SELECT instante, sum(secoes) OVER janela AS secoes, sum(lula) OVER janela AS lula, sum(bolsonaro) OVER janela AS bolsonaro
            FROM secoes WINDOW janela AS (ORDER BY instante)
        ), atualizacoes AS (
            SELECT try_strptime(trim(DT_TOTALIZACAO), '%d/%m/%Y %H:%M:%S') AS instante,
                   try_cast(trim(QT_SECOES_TOT_ACUMULADO) AS BIGINT) AS secoes,
                   try_cast(trim(LULA_QT_VOTOS_TOT_ACUMULADO) AS BIGINT) AS lula,
                   try_cast(trim(JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO) AS BIGINT) AS bolsonaro
            FROM historico WHERE trim(SG_UE_UF)='BR'
        )
        SELECT count(*), sum(CASE WHEN a.secoes=z.secoes AND a.lula=z.lula AND a.bolsonaro=z.bolsonaro THEN 1 ELSE 0 END)
        FROM atualizacoes AS a ASOF LEFT JOIN acumulado AS z ON a.instante >= z.instante
        """
    ).fetchone()
    if total != exact:
        raise SystemExit(f"Reconciliação reprovada: {exact}/{total}")

    delays = connection.execute(
        """SELECT floor(datediff('second', try_strptime(DT_RECEBIMENTO_BU_HOR_TSE, '%d/%m/%Y %H:%M:%S'),
                                  try_strptime(DT_PRIM_TOT_PARCIAL_HOR_TSE, '%d/%m/%Y %H:%M:%S')) / 10) * 10 AS faixa_segundos,
                  count(*) AS secoes
           FROM detalhe WHERE NR_TURNO='2' AND CD_ELEICAO='545' AND CD_CARGO='1' GROUP BY 1 ORDER BY 1"""
    ).fetchall()
    write_csv(AUDIT / "defasagem_bu_primeira_totalizacao.csv", ["faixa_segundos", "secoes"], delays)

    rhythm = connection.execute(
        """SELECT try_cast(NR_TURNO AS INTEGER) AS turno,
                  date_trunc('minute', try_strptime(DT_PRIM_TOT_PARCIAL_HOR_TSE, '%d/%m/%Y %H:%M:%S')) AS minuto,
                  sum(try_cast(QT_VOTOS_NOMINAIS AS BIGINT) + try_cast(QT_VOTOS_LEGENDA AS BIGINT)) AS votos_validos,
                  count(*) AS secoes
           FROM detalhe
           WHERE CD_CARGO='1' AND DT_PRIM_TOT_PARCIAL_HOR_TSE IS NOT NULL AND trim(DT_PRIM_TOT_PARCIAL_HOR_TSE) <> ''
           GROUP BY 1, 2 ORDER BY 1, 2"""
    ).fetchall()
    if {row[0] for row in rhythm} != {1, 2}:
        raise SystemExit("A série por minuto deve conter os dois turnos de 2022")
    write_csv(AUDIT / "ritmo_apuracao_por_minuto.csv", ["turno", "minuto_primeira_totalizacao", "votos_validos", "secoes"], rhythm)
    print(f"Detalhe por seção aprovado: {exact}/{total} atualizações nacionais exatas.")
    print(f"Ritmo por minuto produzido: {len(rhythm):,} pontos nos dois turnos.")


if __name__ == "__main__":
    main()
