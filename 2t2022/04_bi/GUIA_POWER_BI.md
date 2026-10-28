# Guia da camada para Power BI

## Arquivos a importar

Use o conector **Pasta** para cada fato e combine os arquivos Parquet:

- `dados/fato_votos/`: um registro por seção, cargo e opção votável;
- `dados/fato_boletins/`: um registro por seção e cargo;
- `dados/fato_recebimentos/`: quantidade de boletins e eleitores recebidos por segundo, UF e cargo.

As dimensões estão em `dados/dimensoes/` (Parquet) e também em `dados/dimensoes_csv/` (CSV UTF-8).

## Relacionamentos

Crie relacionamentos de um para muitos, com filtro em uma direção:

| Dimensão | Chave | Fatos relacionados |
| --- | --- | --- |
| `dim_uf` | `sg_uf` | todos |
| `dim_localidade` | `id_localidade` | `fato_votos`, `fato_boletins` |
| `dim_cargo` | `cd_cargo` | todos |
| `dim_votavel` | `id_votavel` | `fato_votos` |
| `dim_tempo_recebimento` | `id_tempo_recebimento` | todos |

Não relacione as tabelas fato diretamente entre si. Use as dimensões compartilhadas.

## Medidas DAX iniciais

```DAX
Votos = SUM(fato_votos[qt_votos])

Boletins recebidos = DISTINCTCOUNT(fato_boletins[id_bu_cargo])

Comparecimento recebido = SUM(fato_boletins[qt_comparecimento])

Votos acumulados =
VAR Instante = MAX(dim_tempo_recebimento[dt_bu_recebido])
RETURN
    CALCULATE(
        [Votos],
        FILTER(
            ALLSELECTED(dim_tempo_recebimento[dt_bu_recebido]),
            dim_tempo_recebimento[dt_bu_recebido] <= Instante
        )
    )

Boletins acumulados =
VAR Instante = MAX(dim_tempo_recebimento[dt_bu_recebido])
RETURN
    CALCULATE(
        [Boletins recebidos],
        FILTER(
            ALLSELECTED(dim_tempo_recebimento[dt_bu_recebido]),
            dim_tempo_recebimento[dt_bu_recebido] <= Instante
        )
    )
```

As medidas acima analisam o **recebimento dos BUs**. Nesse contexto, use
`dt_bu_recebido` como eixo. Boletins com o mesmo segundo podem ser agregados para análise,
mas isso não demonstra que formem um lote interno indivisível; a fonte também não permite
ordená-los entre si.

Para reproduzir a **evolução oficial da totalização presidencial nacional**, use
`fontes/historico_totalizacao/Historico_Totalizacao_Presidente_BR_2T_2022.csv` e
`DT_TOTALIZACAO`, como faz `notebooks/analise_evolucao_votos.ipynb`. Não trate
`DT_BU_RECEBIDO` e `DT_TOTALIZACAO` como o mesmo evento: o primeiro registra o recebimento
do boletim e o segundo, a publicação da atualização na totalização oficial.

Antes de publicar um painel, confira `auditoria/RELATORIO_VALIDACAO.md`. Os registros de `alertas_temporais.csv` não foram corrigidos artificialmente: a ordem continua baseada no recebimento informado pela fonte.

Mantenha o filtro de cargo em seleção única ao analisar eleitorado ou comparecimento. A granularidade de `fato_boletins` é seção **por cargo**; somar Presidente e Governador duplicaria esses quantitativos.
