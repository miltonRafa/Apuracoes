#!/usr/bin/env python3
"""Valida a camada BI contra a origem e produz evidências consultáveis."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
BI_ROOT = ROOT / "04_bi"
AUDIT_DIR = BI_ROOT / "auditoria"


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def main() -> None:
    AUDIT_DIR.mkdir(exist_ok=True)
    source_glob = sql_path(ROOT / "02_dados_csv" / "bweb_2t_*.csv")
    votes_glob = sql_path(BI_ROOT / "dados" / "fato_votos" / "**" / "*.parquet")
    bu_glob = sql_path(BI_ROOT / "dados" / "fato_boletins" / "**" / "*.parquet")
    lots_glob = sql_path(BI_ROOT / "dados" / "fato_lotes_recebimento" / "**" / "*.parquet")

    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute(
        f"""
        CREATE TEMP VIEW origem AS
        SELECT * FROM read_csv('{source_glob}', delim=';', header=true, encoding='latin-1',
                              all_varchar=true, union_by_name=true);
        CREATE TEMP VIEW votos_bi AS
        SELECT * FROM read_parquet('{votes_glob}', hive_partitioning=true);
        CREATE TEMP VIEW boletins_bi AS
        SELECT * FROM read_parquet('{bu_glob}', hive_partitioning=true);
        CREATE TEMP VIEW lotes_bi AS
        SELECT * FROM read_parquet('{lots_glob}', hive_partitioning=true);
        """
    )

    # Uma agregação independente da construção da camada permite revisar regras por BU.
    con.execute(
        """
        CREATE TEMP TABLE origem_bu AS
        SELECT
            concat_ws('|',CD_ELEICAO,SG_UF,CD_MUNICIPIO,NR_ZONA,NR_SECAO,CD_CARGO_PERGUNTA) AS id_bu_cargo,
            SG_UF AS sg_uf,
            try_cast(CD_CARGO_PERGUNTA AS SMALLINT) AS cd_cargo,
            try_strptime(DT_BU_RECEBIDO, '%d/%m/%Y %H:%M:%S') AS dt_bu_recebido,
            max(try_cast(QT_APTOS AS BIGINT)) AS qt_aptos,
            max(try_cast(QT_COMPARECIMENTO AS BIGINT)) AS qt_comparecimento,
            max(try_cast(QT_ABSTENCOES AS BIGINT)) AS qt_abstencoes,
            sum(try_cast(QT_VOTOS AS BIGINT)) AS qt_votos
        FROM origem
        GROUP BY id_bu_cargo, SG_UF, CD_CARGO_PERGUNTA, DT_BU_RECEBIDO
        """
    )

    def scalar(query: str):
        return con.execute(query).fetchone()[0]

    checks: list[dict] = []

    def check(name: str, actual, expected, detail: str) -> None:
        checks.append(
            {
                "teste": name,
                "severidade": "ERRO",
                "status": "OK" if actual == expected else "FALHA",
                "obtido": actual,
                "esperado": expected,
                "detalhe": detail,
            }
        )

    def alert(name: str, actual, detail: str) -> None:
        checks.append(
            {
                "teste": name,
                "severidade": "ALERTA",
                "status": "OK" if actual == 0 else "ALERTA",
                "obtido": actual,
                "esperado": 0,
                "detalhe": detail,
            }
        )

    source_rows = scalar("SELECT count(*) FROM origem")
    output_rows = scalar("SELECT count(*) FROM votos_bi")
    check("Quantidade de registros de votos", output_rows, source_rows, "Origem versus fato_votos")

    source_votes = scalar("SELECT sum(try_cast(QT_VOTOS AS HUGEINT)) FROM origem")
    output_votes = scalar("SELECT sum(qt_votos::HUGEINT) FROM votos_bi")
    check("Total de votos", output_votes, source_votes, "Reconciliação integral da medida QT_VOTOS")

    source_bu = scalar("SELECT count(*) FROM origem_bu")
    output_bu = scalar("SELECT count(*) FROM boletins_bi")
    check("Quantidade de boletins por seção/cargo", output_bu, source_bu, "Origem agregada versus fato_boletins")

    duplicate_votes = scalar("SELECT count(*) - count(DISTINCT id_registro_voto) FROM votos_bi")
    check("Chaves duplicadas em fato_votos", duplicate_votes, 0, "A chave inclui seção, cargo, tipo e número do votável")

    duplicate_bu = scalar("SELECT count(*) - count(DISTINCT id_bu_cargo) FROM boletins_bi")
    check("Chaves duplicadas em fato_boletins", duplicate_bu, 0, "Uma linha por seção e cargo")

    inconsistent_metadata = scalar(
        """
        SELECT count(*) FROM (
            SELECT concat_ws('|',CD_ELEICAO,SG_UF,CD_MUNICIPIO,NR_ZONA,NR_SECAO,CD_CARGO_PERGUNTA) AS id,
                   count(DISTINCT concat_ws('|',DT_BU_RECEBIDO,QT_APTOS,QT_COMPARECIMENTO,
                                                QT_ABSTENCOES,NR_URNA_EFETIVADA,DT_EMISSAO_BU)) AS variantes
            FROM origem GROUP BY id HAVING variantes <> 1
        )
        """
    )
    check("Consistência interna dos metadados do BU", inconsistent_metadata, 0, "Linhas de voto do mesmo BU devem repetir os mesmos metadados")

    electorate_errors = scalar(
        "SELECT count(*) FROM boletins_bi WHERE qt_aptos <> qt_comparecimento + qt_abstencoes"
    )
    check("Equação do eleitorado", electorate_errors, 0, "QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES")

    ballot_vote_errors = scalar(
        """
        SELECT count(*) FROM origem_bu
        WHERE qt_votos <> qt_comparecimento
        """
    )
    check("Fechamento de votos por boletim", ballot_vote_errors, 0, "Soma de QT_VOTOS = QT_COMPARECIMENTO")

    null_received = scalar("SELECT count(*) FROM boletins_bi WHERE dt_bu_recebido IS NULL")
    check("Horários de recebimento válidos", null_received, 0, "Necessário para ordenar a apuração")

    source_fingerprint = scalar(
        """
        SELECT bit_xor(hash(concat_ws('|', CD_ELEICAO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO,
                                             CD_CARGO_PERGUNTA, CD_TIPO_VOTAVEL, NR_VOTAVEL, QT_VOTOS)))
        FROM origem
        """
    )
    output_fingerprint = scalar(
        """
        SELECT bit_xor(hash(concat_ws('|', cd_eleicao, sg_uf, cd_municipio, nr_zona, nr_secao,
                                             cd_cargo, cd_tipo_votavel, nr_votavel, qt_votos)))
        FROM votos_bi
        """
    )
    check("Impressão digital dos registros", output_fingerprint, source_fingerprint, "Hash independente de ordem")

    duplicate_lots = scalar(
        """
        SELECT count(*) - count(DISTINCT concat_ws('|',id_tempo_recebimento,sg_uf,cd_cargo))
        FROM lotes_bi
        """
    )
    check("Chaves duplicadas em fato_lotes_recebimento", duplicate_lots, 0, "Uma linha por segundo, UF e cargo")
    lots_ballots = scalar("SELECT sum(qt_boletins_lote) FROM lotes_bi")
    check("Reconciliação de boletins nos lotes", lots_ballots, output_bu, "Soma dos lotes versus fato_boletins")
    lots_turnout = scalar("SELECT sum(qt_comparecimento_lote) FROM lotes_bi")
    ballots_turnout = scalar("SELECT sum(qt_comparecimento) FROM boletins_bi")
    check("Reconciliação de comparecimento nos lotes", lots_turnout, ballots_turnout, "Soma dos lotes versus fato_boletins")

    # Integridade referencial das dimensões.
    dims = {
        "localidade": ("dim_localidade", "id_localidade"),
        "cargo": ("dim_cargo", "cd_cargo"),
        "votável": ("dim_votavel", "id_votavel"),
        "tempo": ("dim_tempo_recebimento", "id_tempo_recebimento"),
    }
    for label, (filename, key) in dims.items():
        path = sql_path(BI_ROOT / "dados" / "dimensoes" / f"{filename}.parquet")
        con.execute(f"CREATE OR REPLACE TEMP VIEW dim_atual AS SELECT * FROM read_parquet('{path}')")
        duplicate_dim = scalar(f"SELECT count(*) - count(DISTINCT {key}) FROM dim_atual")
        check(f"Unicidade da dimensão {label}", duplicate_dim, 0, f"Chave: {key}")
        fact = "boletins_bi" if label in {"localidade", "cargo", "tempo"} else "votos_bi"
        missing_fk = scalar(
            f"SELECT count(*) FROM {fact} f LEFT JOIN dim_atual d ON f.{key}=d.{key} WHERE d.{key} IS NULL"
        )
        check(f"Integridade referencial da dimensão {label}", missing_fk, 0, f"Fato: {fact}")

    uf_path = sql_path(BI_ROOT / "dados" / "dimensoes" / "dim_uf.parquet")
    con.execute(f"CREATE OR REPLACE TEMP VIEW dim_atual AS SELECT * FROM read_parquet('{uf_path}')")
    missing_uf = scalar(
        "SELECT count(*) FROM (SELECT DISTINCT sg_uf FROM votos_bi) f LEFT JOIN dim_atual d USING (sg_uf) WHERE d.sg_uf IS NULL"
    )
    check("Integridade referencial da dimensão UF", missing_uf, 0, "Todas as siglas possuem nome e região")

    for fact_dir in ("fato_votos", "fato_boletins", "fato_lotes_recebimento"):
        partition_files = len(list((BI_ROOT / "dados" / fact_dir).rglob("*.parquet")))
        check(f"Partições publicadas em {fact_dir}", partition_files, 28, "Uma partição Parquet por UF/Exterior")

    # Comparação por UF: facilita localizar qualquer divergência futura.
    comparison_query = """
        WITH o AS (
            SELECT SG_UF AS sg_uf, count(*) AS linhas_origem,
                   sum(try_cast(QT_VOTOS AS HUGEINT)) AS votos_origem
            FROM origem GROUP BY SG_UF
        ), b AS (
            SELECT sg_uf, count(*) AS linhas_bi, sum(qt_votos::HUGEINT) AS votos_bi
            FROM votos_bi GROUP BY sg_uf
        )
        SELECT o.sg_uf, linhas_origem, linhas_bi, votos_origem, votos_bi,
               linhas_bi-linhas_origem AS diferenca_linhas,
               votos_bi-votos_origem AS diferenca_votos
        FROM o FULL JOIN b USING (sg_uf)
        ORDER BY sg_uf
    """
    comparison = con.execute(comparison_query)
    columns = [item[0] for item in comparison.description]
    rows = comparison.fetchall()
    with (AUDIT_DIR / "comparacao_por_uf.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(columns)
        writer.writerows(rows)
    mismatching_ufs = sum(1 for row in rows if row[-2] != 0 or row[-1] != 0)
    check("Reconciliação por UF", mismatching_ufs, 0, "Linhas e votos conferidos para as 28 UFs/Exterior")

    temporal_query = """
        SELECT 'RECEBIMENTO_ANTES_EMISSAO' AS tipo_alerta,
               id_bu_cargo, sg_uf, cd_cargo, dt_encerramento, dt_emissao_bu, dt_bu_recebido,
               datediff('second', dt_emissao_bu, dt_bu_recebido) AS diferenca_segundos
        FROM boletins_bi
        WHERE dt_bu_recebido < dt_emissao_bu
        UNION ALL
        SELECT 'EMISSAO_ANTES_ENCERRAMENTO' AS tipo_alerta,
               id_bu_cargo, sg_uf, cd_cargo, dt_encerramento, dt_emissao_bu, dt_bu_recebido,
               datediff('second', dt_encerramento, dt_emissao_bu) AS diferenca_segundos
        FROM boletins_bi
        WHERE dt_emissao_bu < dt_encerramento
        ORDER BY tipo_alerta, sg_uf, id_bu_cargo
    """
    temporal = con.execute(temporal_query)
    temporal_columns = [item[0] for item in temporal.description]
    temporal_rows = temporal.fetchall()
    with (AUDIT_DIR / "alertas_temporais.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(temporal_columns)
        writer.writerows(temporal_rows)
    received_before_issued = sum(1 for row in temporal_rows if row[0] == "RECEBIMENTO_ANTES_EMISSAO")
    issued_before_closed = sum(1 for row in temporal_rows if row[0] == "EMISSAO_ANTES_ENCERRAMENTO")
    alert("Recebimento anterior à emissão", received_before_issued, "Anomalia da fonte; casos completos em alertas_temporais.csv")
    alert("Emissão anterior ao encerramento", issued_before_closed, "Anomalia da fonte; casos completos em alertas_temporais.csv")

    executed_at = datetime.now(timezone.utc).isoformat()
    failures = sum(item["status"] == "FALHA" for item in checks)
    alerts = sum(item["status"] == "ALERTA" for item in checks)
    overall = "REPROVADO" if failures else ("APROVADO_COM_ALERTAS" if alerts else "APROVADO")
    report = {
        "executado_em_utc": executed_at,
        "status_geral": overall,
        "falhas": failures,
        "alertas": alerts,
        "testes": checks,
    }
    (AUDIT_DIR / "resultado_validacao.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    with (AUDIT_DIR / "resultado_validacao.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=checks[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(checks)

    markdown = [
        "# Relatório de validação da camada BI",
        "",
        f"**Status geral: {report['status_geral']}**",
        "",
        f"Executado em UTC: `{executed_at}`",
        "",
        "| Teste | Severidade | Status | Obtido | Esperado |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for item in checks:
        markdown.append(
            f"| {item['teste']} | {item['severidade']} | {item['status']} | {item['obtido']} | {item['esperado']} |"
        )
    markdown += [
        "",
        "Falhas impedem a aprovação. Alertas identificam anomalias já existentes na fonte e não alteram os valores publicados.",
        "",
        "A ordem da apuração usa `DT_BU_RECEBIDO`. Boletins recebidos no mesmo segundo pertencem ao mesmo lote; o arquivo de origem não permite ordená-los entre si.",
        "",
    ]
    (AUDIT_DIR / "RELATORIO_VALIDACAO.md").write_text("\n".join(markdown), encoding="utf-8")
    con.close()

    print(f"Validação: {report['status_geral']} ({failures} falhas; {alerts} alertas; {len(checks)} controles)")
    if report["status_geral"] == "REPROVADO":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
