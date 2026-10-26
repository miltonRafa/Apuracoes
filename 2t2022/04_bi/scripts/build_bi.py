#!/usr/bin/env python3
"""Constrói a camada analítica sem alterar os CSVs de origem."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
BI_ROOT = ROOT / "04_bi"
SOURCE_DIR = ROOT / "02_dados_csv"
OUTPUT_DIR = BI_ROOT / "dados"
AUDIT_DIR = BI_ROOT / "auditoria"


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_parquet(con: duckdb.DuckDBPyConnection, query: str, destination: Path, partitioned: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = sql_path(destination)
    if partitioned:
        con.execute(
            f"COPY ({query}) TO '{target}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (particao_uf), ROW_GROUP_SIZE 100000)"
        )
    else:
        con.execute(
            f"COPY ({query}) TO '{target}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )


def copy_csv(con: duckdb.DuckDBPyConnection, query: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY ({query}) TO '{sql_path(destination)}' "
        "(FORMAT CSV, HEADER TRUE, DELIMITER ';')"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera a camada Parquet para BI.")
    parser.add_argument("--threads", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    args = parser.parse_args()

    sources = sorted(SOURCE_DIR.glob("bweb_2t_*.csv"))
    if len(sources) != 28:
        raise SystemExit(f"Esperados 28 CSVs em {SOURCE_DIR}; encontrados {len(sources)}.")

    BI_ROOT.mkdir(exist_ok=True)
    AUDIT_DIR.mkdir(exist_ok=True)
    staging = BI_ROOT / f".dados_construcao_{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    con = duckdb.connect()
    con.execute(f"SET threads={args.threads}")
    con.execute("SET preserve_insertion_order=false")
    source_glob = sql_path(SOURCE_DIR / "bweb_2t_*.csv")

    try:
        con.execute(
            f"""
            CREATE TEMP VIEW origem AS
            SELECT *
            FROM read_csv(
                '{source_glob}', delim=';', header=true, encoding='latin-1',
                all_varchar=true, union_by_name=true, filename=true
            )
            """
        )
        con.execute(
            """
            CREATE TEMP VIEW base AS
            SELECT
                concat_ws('|', CD_ELEICAO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO) AS id_secao,
                concat_ws('|', CD_ELEICAO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, CD_CARGO_PERGUNTA) AS id_bu_cargo,
                concat_ws('|', SG_UF, CD_MUNICIPIO) AS id_localidade,
                concat_ws('|', CD_ELEICAO, SG_UF, CD_CARGO_PERGUNTA, CD_TIPO_VOTAVEL, NR_VOTAVEL) AS id_votavel,
                concat_ws('|', CD_ELEICAO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO,
                          CD_CARGO_PERGUNTA, CD_TIPO_VOTAVEL, NR_VOTAVEL) AS id_registro_voto,
                try_cast(ANO_ELEICAO AS SMALLINT) AS ano_eleicao,
                try_cast(CD_TIPO_ELEICAO AS SMALLINT) AS cd_tipo_eleicao,
                NM_TIPO_ELEICAO AS nm_tipo_eleicao,
                try_cast(CD_PLEITO AS INTEGER) AS cd_pleito,
                try_strptime(DT_PLEITO, '%d/%m/%Y')::DATE AS dt_pleito,
                try_cast(NR_TURNO AS SMALLINT) AS nr_turno,
                try_cast(CD_ELEICAO AS INTEGER) AS cd_eleicao,
                DS_ELEICAO AS ds_eleicao,
                SG_UF AS sg_uf,
                try_cast(CD_MUNICIPIO AS INTEGER) AS cd_municipio,
                NM_MUNICIPIO AS nm_municipio,
                try_cast(NR_ZONA AS INTEGER) AS nr_zona,
                try_cast(NR_SECAO AS INTEGER) AS nr_secao,
                try_cast(NR_LOCAL_VOTACAO AS INTEGER) AS nr_local_votacao,
                try_cast(CD_CARGO_PERGUNTA AS SMALLINT) AS cd_cargo,
                DS_CARGO_PERGUNTA AS nm_cargo,
                CASE WHEN NR_PARTIDO IN ('-1', '-3', '', '#NULO#', '#NE') THEN NULL
                     ELSE try_cast(NR_PARTIDO AS SMALLINT) END AS nr_partido,
                nullif(nullif(SG_PARTIDO, '#NULO#'), '#NE') AS sg_partido,
                nullif(nullif(NM_PARTIDO, '#NULO#'), '#NE') AS nm_partido,
                try_strptime(DT_BU_RECEBIDO, '%d/%m/%Y %H:%M:%S') AS dt_bu_recebido,
                try_cast(QT_APTOS AS INTEGER) AS qt_aptos,
                try_cast(QT_COMPARECIMENTO AS INTEGER) AS qt_comparecimento,
                try_cast(QT_ABSTENCOES AS INTEGER) AS qt_abstencoes,
                try_cast(CD_TIPO_URNA AS SMALLINT) AS cd_tipo_urna,
                DS_TIPO_URNA AS nm_tipo_urna,
                try_cast(CD_TIPO_VOTAVEL AS SMALLINT) AS cd_tipo_votavel,
                DS_TIPO_VOTAVEL AS nm_tipo_votavel,
                try_cast(NR_VOTAVEL AS INTEGER) AS nr_votavel,
                NM_VOTAVEL AS nm_votavel,
                try_cast(QT_VOTOS AS INTEGER) AS qt_votos,
                try_cast(NR_URNA_EFETIVADA AS INTEGER) AS nr_urna_efetivada,
                nullif(nullif(CD_CARGA_1_URNA_EFETIVADA, '#NULO#'), '#NE') AS cd_carga_1_urna,
                nullif(nullif(CD_CARGA_2_URNA_EFETIVADA, '#NULO#'), '#NE') AS cd_carga_2_urna,
                nullif(nullif(CD_FLASHCARD_URNA_EFETIVADA, '#NULO#'), '#NE') AS cd_flashcard_urna,
                try_strptime(nullif(nullif(DT_CARGA_URNA_EFETIVADA, '#NULO#'), '#NE'), '%d/%m/%Y %H:%M:%S') AS dt_carga_urna,
                nullif(nullif(DS_AGREGADAS, '#NULO#'), '#NE') AS ds_secoes_agregadas,
                try_strptime(nullif(nullif(DT_ABERTURA, '#NULO#'), '#NE'), '%d/%m/%Y %H:%M:%S') AS dt_abertura,
                try_strptime(nullif(nullif(DT_ENCERRAMENTO, '#NULO#'), '#NE'), '%d/%m/%Y %H:%M:%S') AS dt_encerramento,
                try_cast(QT_ELEITORES_BIOMETRIA_NH AS INTEGER) AS qt_eleitores_biometria_nh,
                try_strptime(DT_EMISSAO_BU, '%d/%m/%Y %H:%M:%S') AS dt_emissao_bu,
                CASE WHEN NR_JUNTA_APURADORA IN ('-1', '-3', '', '#NULO#', '#NE') THEN NULL
                     ELSE try_cast(NR_JUNTA_APURADORA AS INTEGER) END AS nr_junta_apuradora,
                CASE WHEN NR_TURMA_APURADORA IN ('-1', '-3', '', '#NULO#', '#NE') THEN NULL
                     ELSE try_cast(NR_TURMA_APURADORA AS INTEGER) END AS nr_turma_apuradora,
                regexp_extract(filename, '[^/]+$') AS arquivo_origem
            FROM origem
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE boletins AS
            WITH unicos AS (
                SELECT
                    id_bu_cargo, id_secao, id_localidade, ano_eleicao, cd_eleicao, nr_turno,
                    sg_uf, cd_municipio, nr_zona, nr_secao, nr_local_votacao,
                    cd_cargo, dt_bu_recebido,
                    any_value(qt_aptos) AS qt_aptos,
                    any_value(qt_comparecimento) AS qt_comparecimento,
                    any_value(qt_abstencoes) AS qt_abstencoes,
                    any_value(cd_tipo_urna) AS cd_tipo_urna,
                    any_value(nm_tipo_urna) AS nm_tipo_urna,
                    any_value(nr_urna_efetivada) AS nr_urna_efetivada,
                    any_value(cd_carga_1_urna) AS cd_carga_1_urna,
                    any_value(cd_carga_2_urna) AS cd_carga_2_urna,
                    any_value(cd_flashcard_urna) AS cd_flashcard_urna,
                    any_value(dt_carga_urna) AS dt_carga_urna,
                    any_value(ds_secoes_agregadas) AS ds_secoes_agregadas,
                    any_value(dt_abertura) AS dt_abertura,
                    any_value(dt_encerramento) AS dt_encerramento,
                    any_value(qt_eleitores_biometria_nh) AS qt_eleitores_biometria_nh,
                    any_value(dt_emissao_bu) AS dt_emissao_bu,
                    any_value(nr_junta_apuradora) AS nr_junta_apuradora,
                    any_value(nr_turma_apuradora) AS nr_turma_apuradora,
                    any_value(arquivo_origem) AS arquivo_origem
                FROM base
                GROUP BY id_bu_cargo, id_secao, id_localidade, ano_eleicao, cd_eleicao, nr_turno,
                         sg_uf, cd_municipio, nr_zona, nr_secao, nr_local_votacao,
                         cd_cargo, dt_bu_recebido
            )
            SELECT
                *,
                cast(strftime(dt_bu_recebido, '%Y%m%d%H%M%S') AS BIGINT) AS id_tempo_recebimento,
                dense_rank() OVER (PARTITION BY cd_cargo ORDER BY dt_bu_recebido) AS nr_lote_nacional,
                dense_rank() OVER (PARTITION BY cd_cargo, sg_uf ORDER BY dt_bu_recebido) AS nr_lote_uf,
                count(*) OVER (PARTITION BY cd_cargo, dt_bu_recebido) AS qt_bu_mesmo_instante_nacional,
                count(*) OVER (PARTITION BY cd_cargo, sg_uf, dt_bu_recebido) AS qt_bu_mesmo_instante_uf,
                datediff('second', min(dt_bu_recebido) OVER (PARTITION BY cd_cargo), dt_bu_recebido) AS segundos_desde_inicio_cargo
            FROM unicos
            """
        )

        fato_votos = """
            SELECT
                id_registro_voto, id_bu_cargo, id_secao, id_localidade, id_votavel,
                cast(strftime(dt_bu_recebido, '%Y%m%d%H%M%S') AS BIGINT) AS id_tempo_recebimento,
                ano_eleicao, cd_eleicao, nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao,
                nr_local_votacao, cd_cargo, cd_tipo_votavel, nr_votavel, nr_partido,
                dt_bu_recebido, qt_votos, arquivo_origem,
                sg_uf AS particao_uf
            FROM base
        """
        fato_boletins = "SELECT *, sg_uf AS particao_uf FROM boletins"
        copy_parquet(con, fato_votos, staging / "fato_votos", partitioned=True)
        copy_parquet(con, fato_boletins, staging / "fato_boletins", partitioned=True)

        dimensions = {
            "dim_uf": """
                SELECT * FROM (VALUES
                    ('AC','Acre','Norte',1), ('AL','Alagoas','Nordeste',2), ('AM','Amazonas','Norte',3),
                    ('AP','Amapá','Norte',4), ('BA','Bahia','Nordeste',5), ('CE','Ceará','Nordeste',6),
                    ('DF','Distrito Federal','Centro-Oeste',7), ('ES','Espírito Santo','Sudeste',8),
                    ('GO','Goiás','Centro-Oeste',9), ('MA','Maranhão','Nordeste',10),
                    ('MG','Minas Gerais','Sudeste',11), ('MS','Mato Grosso do Sul','Centro-Oeste',12),
                    ('MT','Mato Grosso','Centro-Oeste',13), ('PA','Pará','Norte',14),
                    ('PB','Paraíba','Nordeste',15), ('PE','Pernambuco','Nordeste',16),
                    ('PI','Piauí','Nordeste',17), ('PR','Paraná','Sul',18),
                    ('RJ','Rio de Janeiro','Sudeste',19), ('RN','Rio Grande do Norte','Nordeste',20),
                    ('RO','Rondônia','Norte',21), ('RR','Roraima','Norte',22),
                    ('RS','Rio Grande do Sul','Sul',23), ('SC','Santa Catarina','Sul',24),
                    ('SE','Sergipe','Nordeste',25), ('SP','São Paulo','Sudeste',26),
                    ('TO','Tocantins','Norte',27), ('ZZ','Exterior','Exterior',28)
                ) AS t(sg_uf, nm_uf, nm_regiao, nr_ordem_uf)
            """,
            "dim_localidade": """
                SELECT id_localidade, sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio
                FROM base GROUP BY id_localidade, sg_uf, cd_municipio
            """,
            "dim_cargo": """
                SELECT cd_cargo, any_value(nm_cargo) AS nm_cargo
                FROM base GROUP BY cd_cargo
            """,
            "dim_votavel": """
                SELECT id_votavel, cd_eleicao, sg_uf, cd_cargo, cd_tipo_votavel,
                       nr_votavel, any_value(nm_votavel) AS nm_votavel,
                       any_value(nm_tipo_votavel) AS nm_tipo_votavel,
                       any_value(nr_partido) AS nr_partido,
                       any_value(sg_partido) AS sg_partido,
                       any_value(nm_partido) AS nm_partido
                FROM base
                GROUP BY id_votavel, cd_eleicao, sg_uf, cd_cargo, cd_tipo_votavel, nr_votavel
            """,
            "dim_tempo_recebimento": """
                SELECT DISTINCT
                    cast(strftime(dt_bu_recebido, '%Y%m%d%H%M%S') AS BIGINT) AS id_tempo_recebimento,
                    dt_bu_recebido,
                    dt_bu_recebido::DATE AS dt_recebimento,
                    year(dt_bu_recebido) AS nr_ano,
                    month(dt_bu_recebido) AS nr_mes,
                    day(dt_bu_recebido) AS nr_dia,
                    hour(dt_bu_recebido) AS nr_hora,
                    minute(dt_bu_recebido) AS nr_minuto,
                    second(dt_bu_recebido) AS nr_segundo,
                    date_trunc('minute', dt_bu_recebido) AS dt_minuto
                FROM base
            """,
        }
        for name, query in dimensions.items():
            copy_parquet(con, query, staging / "dimensoes" / f"{name}.parquet")
            copy_csv(con, query, staging / "dimensoes_csv" / f"{name}.csv")

        lote_query = """
            SELECT
                id_tempo_recebimento, dt_bu_recebido, sg_uf, cd_cargo,
                min(nr_lote_nacional) AS nr_lote_nacional,
                min(nr_lote_uf) AS nr_lote_uf,
                count(*) AS qt_boletins_lote,
                sum(qt_aptos) AS qt_aptos_lote,
                sum(qt_comparecimento) AS qt_comparecimento_lote,
                sum(qt_abstencoes) AS qt_abstencoes_lote,
                sg_uf AS particao_uf
            FROM boletins
            GROUP BY id_tempo_recebimento, dt_bu_recebido, sg_uf, cd_cargo
        """
        copy_parquet(con, lote_query, staging / "fato_lotes_recebimento", partitioned=True)

        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        staging.rename(OUTPUT_DIR)

        manifest_path = AUDIT_DIR / "manifesto_fontes.csv"
        with manifest_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["arquivo", "tamanho_bytes", "sha256"])
            for source in sources:
                writer.writerow([source.name, source.stat().st_size, sha256(source)])

        metadata = {
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
            "duckdb_versao": duckdb.__version__,
            "arquivos_origem": len(sources),
            "pasta_origem": str(SOURCE_DIR),
            "pasta_saida": str(OUTPUT_DIR),
            "regra_ordem_apuracao": "DT_BU_RECEBIDO; empates no mesmo segundo formam um único lote",
        }
        (AUDIT_DIR / "metadados_execucao.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Camada BI gerada em {OUTPUT_DIR}")
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
