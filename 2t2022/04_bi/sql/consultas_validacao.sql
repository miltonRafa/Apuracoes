-- Execute a partir da raiz do projeto com DuckDB.
-- Os arquivos Parquet são a camada publicada; os CSVs originais permanecem imutáveis.

CREATE OR REPLACE VIEW fato_votos AS
SELECT * FROM read_parquet('04_bi/dados/fato_votos/**/*.parquet', hive_partitioning=true);

CREATE OR REPLACE VIEW fato_boletins AS
SELECT * FROM read_parquet('04_bi/dados/fato_boletins/**/*.parquet', hive_partitioning=true);

-- Totais gerais.
SELECT count(*) AS registros, sum(qt_votos) AS votos
FROM fato_votos;

-- Fechamento do eleitorado: deve retornar zero linhas.
SELECT id_bu_cargo, qt_aptos, qt_comparecimento, qt_abstencoes
FROM fato_boletins
WHERE qt_aptos <> qt_comparecimento + qt_abstencoes;

-- Período e quantidade de boletins por cargo.
SELECT cd_cargo, count(*) AS boletins,
       min(dt_bu_recebido) AS primeiro_recebimento,
       max(dt_bu_recebido) AS ultimo_recebimento
FROM fato_boletins
GROUP BY cd_cargo
ORDER BY cd_cargo;

-- Empates de ordem: cada instante é um lote indivisível na fonte.
SELECT cd_cargo, dt_bu_recebido, count(*) AS boletins_no_mesmo_segundo
FROM fato_boletins
GROUP BY cd_cargo, dt_bu_recebido
HAVING count(*) > 1
ORDER BY boletins_no_mesmo_segundo DESC, dt_bu_recebido;
