#!/usr/bin/env python3
"""Valida a camada BI contra a origem e produz evidências consultáveis."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
BI_ROOT = ROOT / "04_bi"
AUDIT_DIR = BI_ROOT / "auditoria"
EXPECTED_UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
}


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def write_text_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_csv_atomic(path: Path, columns: list[str], rows: list[tuple]) -> None:
    temporary = path.with_name(path.name + ".part")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter=";", lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
    temporary.replace(path)


def main() -> None:
    AUDIT_DIR.mkdir(exist_ok=True)
    source_glob = sql_path(ROOT / "02_dados_csv" / "bweb_2t_*.csv")
    votes_glob = sql_path(BI_ROOT / "dados" / "fato_votos" / "**" / "*.parquet")
    bu_glob = sql_path(BI_ROOT / "dados" / "fato_boletins" / "**" / "*.parquet")
    receipts_glob = sql_path(BI_ROOT / "dados" / "fato_recebimentos" / "**" / "*.parquet")

    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute(
        f"""
        CREATE TEMP VIEW origem AS
        SELECT * FROM read_csv('{source_glob}', delim=';', header=true, encoding='latin-1',
                              all_varchar=true, union_by_name=true, filename=true);
        CREATE TEMP VIEW votos_bi AS
        SELECT * FROM read_parquet('{votes_glob}', hive_partitioning=true);
        CREATE TEMP VIEW boletins_bi AS
        SELECT * FROM read_parquet('{bu_glob}', hive_partitioning=true);
        CREATE TEMP VIEW recebimentos_bi AS
        SELECT * FROM read_parquet('{receipts_glob}', hive_partitioning=true);
        """
    )

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
        checks.append({
            "teste": name,
            "severidade": "ERRO",
            "status": "OK" if actual == expected else "FALHA",
            "obtido": actual,
            "esperado": expected,
            "detalhe": detail,
        })

    def alert(name: str, actual, detail: str) -> None:
        checks.append({
            "teste": name,
            "severidade": "ALERTA",
            "status": "OK" if actual == 0 else "ALERTA",
            "obtido": actual,
            "esperado": 0,
            "detalhe": detail,
        })

    # Escopo e parse: evita que TRY_CAST transforme silenciosamente dado inválido em NULL.
    source_files = scalar("SELECT count(DISTINCT filename) FROM origem")
    check("Quantidade de arquivos de origem", source_files, 28, "Um CSV por UF/Exterior")
    source_ufs = {row[0] for row in con.execute("SELECT DISTINCT SG_UF FROM origem").fetchall()}
    uf_set_errors = len(source_ufs.symmetric_difference(EXPECTED_UFS))
    check("Abrangências da origem", uf_set_errors, 0, "Conjunto exato das 27 UFs e Exterior")
    filename_mismatches = scalar(
        """
        SELECT count(*) FROM origem
        WHERE regexp_extract(filename, 'bweb_2t_([A-Z]{2})_[0-9]{12}\\.csv$', 1) <> SG_UF
           OR regexp_extract(filename, 'bweb_2t_[A-Z]{2}_[0-9]{12}\\.csv$') = ''
        """
    )
    check("UF coerente com o nome do arquivo", filename_mismatches, 0, "SG_UF versus arquivo fonte")
    scope_errors = scalar(
        """
        SELECT count(*) FROM origem
        WHERE ANO_ELEICAO <> '2022' OR NR_TURNO <> '2' OR DT_PLEITO <> '30/10/2022'
           OR NOT (
               (CD_ELEICAO = '545' AND CD_CARGO_PERGUNTA = '1')
               OR (CD_ELEICAO = '547' AND CD_CARGO_PERGUNTA = '3')
           )
        """
    )
    check("Escopo eleitoral da origem", scope_errors, 0, "Presidente e Governador, segundo turno de 2022")

    numeric_fields = [
        "ANO_ELEICAO", "CD_TIPO_ELEICAO", "CD_PLEITO", "NR_TURNO", "CD_ELEICAO",
        "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO", "CD_CARGO_PERGUNTA",
        "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "CD_TIPO_URNA", "CD_TIPO_VOTAVEL",
        "NR_VOTAVEL", "QT_VOTOS", "NR_URNA_EFETIVADA", "QT_ELEITORES_BIOMETRIA_NH",
    ]
    numeric_condition = " OR ".join(
        f"({field} IS NULL OR try_cast({field} AS BIGINT) IS NULL)" for field in numeric_fields
    )
    parse_numeric_errors = scalar(f"SELECT count(*) FROM origem WHERE {numeric_condition}")
    check("Conversão dos campos numéricos obrigatórios", parse_numeric_errors, 0, "Nenhum valor vira NULL no parse")
    date_condition = " OR ".join([
        "try_strptime(DT_PLEITO, '%d/%m/%Y') IS NULL",
        "try_strptime(DT_BU_RECEBIDO, '%d/%m/%Y %H:%M:%S') IS NULL",
        "(DT_EMISSAO_BU IS NOT NULL AND try_strptime(DT_EMISSAO_BU, '%d/%m/%Y %H:%M:%S') IS NULL)",
    ])
    parse_date_errors = scalar(f"SELECT count(*) FROM origem WHERE {date_condition}")
    check("Conversão das datas obrigatórias", parse_date_errors, 0, "Datas necessárias ao modelo são válidas")

    optional_numeric_fields = ["NR_PARTIDO", "NR_JUNTA_APURADORA", "NR_TURMA_APURADORA"]
    optional_numeric_condition = " OR ".join(
        f"({field} IS NOT NULL AND {field} NOT IN ('-1', '-3', '', '#NULO#', '#NE') "
        f"AND try_cast({field} AS BIGINT) IS NULL)"
        for field in optional_numeric_fields
    )
    optional_numeric_errors = scalar(
        f"SELECT count(*) FROM origem WHERE {optional_numeric_condition}"
    )
    check(
        "Conversão dos campos numéricos opcionais preenchidos",
        optional_numeric_errors,
        0,
        "Valores preenchidos não podem virar NULL no parse",
    )
    optional_date_fields = [
        "DT_CARGA_URNA_EFETIVADA",
        "DT_ABERTURA",
        "DT_ENCERRAMENTO",
    ]
    optional_date_condition = " OR ".join(
        f"({field} IS NOT NULL AND {field} NOT IN ('', '#NULO#', '#NE') "
        f"AND try_strptime({field}, '%d/%m/%Y %H:%M:%S') IS NULL)"
        for field in optional_date_fields
    )
    optional_date_errors = scalar(
        f"SELECT count(*) FROM origem WHERE {optional_date_condition}"
    )
    check(
        "Conversão das datas opcionais preenchidas",
        optional_date_errors,
        0,
        "Datas preenchidas não podem virar NULL no parse",
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
    check("Chaves duplicadas em fato_votos", duplicate_votes, 0, "Seção, cargo, tipo e número do votável")
    duplicate_bu = scalar("SELECT count(*) - count(DISTINCT id_bu_cargo) FROM boletins_bi")
    check("Chaves duplicadas em fato_boletins", duplicate_bu, 0, "Uma linha por seção e cargo")

    metadata_fields = [
        "DT_BU_RECEBIDO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "CD_TIPO_URNA",
        "DS_TIPO_URNA", "NR_URNA_EFETIVADA", "CD_CARGA_1_URNA_EFETIVADA",
        "CD_CARGA_2_URNA_EFETIVADA", "CD_FLASHCARD_URNA_EFETIVADA", "DT_CARGA_URNA_EFETIVADA",
        "DS_AGREGADAS", "DT_ABERTURA", "DT_ENCERRAMENTO", "QT_ELEITORES_BIOMETRIA_NH",
        "DT_EMISSAO_BU", "NR_JUNTA_APURADORA", "NR_TURMA_APURADORA", "filename",
    ]
    metadata_value = ", ".join(f"coalesce({field}, '<NULL>')" for field in metadata_fields)
    inconsistent_metadata = scalar(
        f"""
        SELECT count(*) FROM (
            SELECT concat_ws('|',CD_ELEICAO,SG_UF,CD_MUNICIPIO,NR_ZONA,NR_SECAO,CD_CARGO_PERGUNTA) AS id,
                   count(DISTINCT concat_ws('|', {metadata_value})) AS variantes
            FROM origem GROUP BY id HAVING variantes <> 1
        )
        """
    )
    check("Consistência interna de todos os metadados do BU", inconsistent_metadata, 0, "Campos repetidos não podem variar dentro do BU")

    required_nulls = scalar(
        """
        SELECT count(*) FROM boletins_bi
        WHERE id_bu_cargo IS NULL OR sg_uf IS NULL OR cd_cargo IS NULL OR dt_bu_recebido IS NULL
           OR qt_aptos IS NULL OR qt_comparecimento IS NULL OR qt_abstencoes IS NULL
           OR arquivo_origem IS NULL
        """
    )
    check("Campos obrigatórios em fato_boletins", required_nulls, 0, "Parse e agregação não podem gerar NULL")
    missing_emission = scalar("SELECT count(*) FROM boletins_bi WHERE dt_emissao_bu IS NULL")
    alert("Horário de emissão ausente", missing_emission, "Ausência preservada da fonte; não é erro de conversão")
    required_vote_nulls = scalar(
        """
        SELECT count(*) FROM votos_bi
        WHERE id_registro_voto IS NULL OR id_bu_cargo IS NULL OR sg_uf IS NULL OR cd_cargo IS NULL
           OR cd_tipo_votavel IS NULL OR nr_votavel IS NULL OR dt_bu_recebido IS NULL
           OR qt_votos IS NULL OR qt_votos < 0
        """
    )
    check("Campos obrigatórios em fato_votos", required_vote_nulls, 0, "Votos não nulos e não negativos")
    electorate_errors = scalar(
        """
        SELECT count(*) FROM boletins_bi
        WHERE qt_aptos IS NULL OR qt_comparecimento IS NULL OR qt_abstencoes IS NULL
           OR qt_aptos <> qt_comparecimento + qt_abstencoes
        """
    )
    check("Equação do eleitorado", electorate_errors, 0, "QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES")
    ballot_vote_errors = scalar(
        """
        SELECT count(*) FROM origem_bu
        WHERE qt_votos IS NULL OR qt_comparecimento IS NULL OR qt_votos <> qt_comparecimento
        """
    )
    check("Fechamento de votos por boletim", ballot_vote_errors, 0, "Soma de QT_VOTOS = QT_COMPARECIMENTO")

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

    duplicate_receipts = scalar(
        """
        SELECT count(*) - count(DISTINCT concat_ws('|',id_tempo_recebimento,sg_uf,cd_cargo))
        FROM recebimentos_bi
        """
    )
    check("Chaves duplicadas em fato_recebimentos", duplicate_receipts, 0, "Uma linha por segundo, UF e cargo")
    receipt_ballots = scalar("SELECT sum(qt_boletins_recebidos) FROM recebimentos_bi")
    check("Reconciliação de boletins recebidos", receipt_ballots, output_bu, "Agregado por instante versus fato_boletins")
    receipt_turnout = scalar("SELECT sum(qt_comparecimento_recebido) FROM recebimentos_bi")
    ballots_turnout = scalar("SELECT sum(qt_comparecimento) FROM boletins_bi")
    check("Reconciliação do comparecimento recebido", receipt_turnout, ballots_turnout, "Agregado por instante versus fato_boletins")

    descriptive_variants = scalar(
        """
        SELECT sum(erros) FROM (
            SELECT count(*) AS erros FROM (
                SELECT SG_UF, CD_MUNICIPIO FROM origem GROUP BY 1,2 HAVING count(DISTINCT NM_MUNICIPIO) <> 1
            )
            UNION ALL
            SELECT count(*) FROM (
                SELECT CD_CARGO_PERGUNTA FROM origem GROUP BY 1 HAVING count(DISTINCT DS_CARGO_PERGUNTA) <> 1
            )
            UNION ALL
            SELECT count(*) FROM (
                SELECT CD_ELEICAO, SG_UF, CD_CARGO_PERGUNTA, CD_TIPO_VOTAVEL, NR_VOTAVEL
                FROM origem GROUP BY 1,2,3,4,5
                HAVING count(DISTINCT concat_ws('|', NM_VOTAVEL, DS_TIPO_VOTAVEL, NR_PARTIDO,
                                                     SG_PARTIDO, NM_PARTIDO)) <> 1
            )
        )
        """
    )
    check("Consistência dos atributos das dimensões", descriptive_variants, 0, "ANY_VALUE só é usado quando há uma única variante")

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

    for fact_view, fact_dir in (
        ("votos_bi", "fato_votos"),
        ("boletins_bi", "fato_boletins"),
        ("recebimentos_bi", "fato_recebimentos"),
    ):
        partition_ufs = scalar(f"SELECT count(DISTINCT particao_uf) FROM {fact_view}")
        check(f"Partições lógicas em {fact_dir}", partition_ufs, 28, "Uma abrangência lógica por UF/Exterior")

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
    comparison_columns = [item[0] for item in comparison.description]
    comparison_rows = comparison.fetchall()
    write_csv_atomic(AUDIT_DIR / "comparacao_por_uf.csv", comparison_columns, comparison_rows)
    mismatching_ufs = sum(1 for row in comparison_rows if row[-2] != 0 or row[-1] != 0)
    check("Reconciliação por UF", mismatching_ufs, 0, "Linhas e votos conferidos para as 28 abrangências")

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
    write_csv_atomic(AUDIT_DIR / "alertas_temporais.csv", temporal_columns, temporal_rows)
    received_before_issued = sum(row[0] == "RECEBIMENTO_ANTES_EMISSAO" for row in temporal_rows)
    issued_before_closed = sum(row[0] == "EMISSAO_ANTES_ENCERRAMENTO" for row in temporal_rows)
    alert("Recebimento anterior à emissão", received_before_issued, "Anomalia da fonte; casos em alertas_temporais.csv")
    alert("Emissão anterior ao encerramento", issued_before_closed, "Anomalia da fonte; casos em alertas_temporais.csv")

    failures = sum(item["status"] == "FALHA" for item in checks)
    alerts = sum(item["status"] == "ALERTA" for item in checks)
    overall = "REPROVADO" if failures else ("APROVADO_COM_ALERTAS" if alerts else "APROVADO")
    report = {"status_geral": overall, "falhas": failures, "alertas": alerts, "testes": checks}
    write_text_atomic(
        AUDIT_DIR / "resultado_validacao.json",
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
    )
    result_columns = list(checks[0])
    result_rows = [tuple(item[column] for column in result_columns) for item in checks]
    write_csv_atomic(AUDIT_DIR / "resultado_validacao.csv", result_columns, result_rows)

    markdown = [
        "# Relatório de validação da camada BI",
        "",
        f"**Status geral: {overall}**",
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
        "Falhas impedem a aprovação. Alertas registram anomalias presentes na fonte e não alteram os valores.",
        "",
        "`DT_BU_RECEBIDO` é o horário de recebimento informado pela fonte. Registros no mesmo segundo podem ser agregados para análise, mas a fonte não demonstra um lote indivisível nem fornece ordem interna entre eles.",
        "",
    ]
    write_text_atomic(AUDIT_DIR / "RELATORIO_VALIDACAO.md", "\n".join(markdown))
    con.close()

    print(f"Validação: {overall} ({failures} falhas; {alerts} alertas; {len(checks)} controles)")
    if overall == "REPROVADO":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
