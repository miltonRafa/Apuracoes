#!/usr/bin/env python3
"""Gera e executa o notebook de evolução dos votos."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = ROOT / "04_bi" / "notebooks"
NOTEBOOK_PATH = NOTEBOOK_DIR / "analise_evolucao_votos.ipynb"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip())


def main() -> None:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    notebook = nbf.v4.new_notebook()
    notebook.metadata = {
        "kernelspec": {
            "display_name": "Python 3 (Apurações)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    }
    notebook.cells = [
        markdown(
            """
            # Evolução dos votos por candidato

            Este notebook reconstrói a evolução da apuração do 2º turno de 2022 usando
            `DT_BU_RECEBIDO`, que representa o recebimento do boletim de urna. Cada candidato
            aparece em uma linha própria.

            **Critérios:** somente votos nominais (`CD_TIPO_VOTAVEL = 1`); cada horário distinto
            de `DT_BU_RECEBIDO` forma uma atualização; eventos recebidos no mesmo segundo
            permanecem no mesmo lote. Os votos são acumulados em ordem crescente de recebimento,
            sem inventar uma ordem entre boletins que possuem exatamente o mesmo horário.
            """
        ),
        code(
            '''
            from pathlib import Path

            import duckdb
            import pandas as pd
            import plotly.graph_objects as go
            import plotly.io as pio
            from IPython.display import display

            pio.renderers.default = "plotly_mimetype"

            def localizar_raiz(inicio: Path) -> Path:
                inicio = inicio.resolve()
                for pasta in (inicio, *inicio.parents):
                    if (pasta / "04_bi" / "dados" / "fato_votos").exists():
                        return pasta
                raise FileNotFoundError("Não foi possível localizar 04_bi/dados/fato_votos")

            RAIZ = localizar_raiz(Path.cwd())
            FATOS = RAIZ / "04_bi" / "dados" / "fato_votos" / "**" / "*.parquet"
            DIM_VOTAVEL = RAIZ / "04_bi" / "dados" / "dimensoes" / "dim_votavel.parquet"

            pd.set_option("display.max_rows", 20)
            pd.set_option("display.float_format", lambda valor: f"{valor:,.2f}")

            CONFIG_GRAFICO = {
                "scrollZoom": True,
                "displayModeBar": True,
                "displaylogo": False,
                "responsive": True,
                "doubleClick": "reset+autosize",
                "toImageButtonOptions": {"format": "png", "scale": 2},
            }

            def configurar_replay(figura, titulo, eixo_y):
                figura.update_layout(
                    title={"text": titulo, "x": 0.02, "xanchor": "left"},
                    height=650,
                    template="plotly_white",
                    hovermode="closest",
                    hoverdistance=30,
                    spikedistance=-1,
                    dragmode="zoom",
                    legend={
                        "title": {"text": "Candidato — duplo clique para isolar"},
                        "orientation": "h",
                        "y": 1.08,
                        "itemclick": "toggle",
                        "itemdoubleclick": "toggleothers",
                    },
                    margin={"l": 75, "r": 35, "t": 135, "b": 70},
                    xaxis={
                        "title": "Ordem original das atualizações",
                        "type": "linear",
                        "tickformat": ",d",
                        "showspikes": True,
                        "spikemode": "across",
                        "spikesnap": "data",
                    },
                    yaxis={
                        "title": eixo_y,
                        "rangemode": "tozero",
                        "separatethousands": True,
                        "showspikes": True,
                        "spikemode": "across",
                        "spikesnap": "data",
                    },
                )
                return figura

            print(f"Raiz localizada: {RAIZ}")
            '''
        ),
        markdown(
            """
            ## Parâmetros

            O padrão mostra Presidente no Brasil inteiro. Para analisar uma UF, altere `UF`
            para uma sigla como `"SP"`. Para Governador, use `CARGO = 3` e selecione uma UF.
            """
        ),
        code(
            '''
            CARGO = 1  # 1 = Presidente; 3 = Governador
            UF = None  # None = Brasil inteiro; exemplo: "SP"

            if CARGO == 3 and UF is None:
                print("Aviso: para Governador, selecione uma UF para evitar misturar disputas estaduais.")
            '''
        ),
        markdown("## Extração e preparação da série temporal"),
        code(
            '''
            con = duckdb.connect()
            caminho_fatos = str(FATOS).replace("'", "''")
            caminho_dim = str(DIM_VOTAVEL).replace("'", "''")

            filtro_uf = "AND v.sg_uf = ?" if UF else ""
            parametros = [CARGO] + ([UF.upper()] if UF else [])

            consulta_instantes = f"""
                SELECT DISTINCT v.dt_bu_recebido AS instante
                FROM read_parquet('{caminho_fatos}', hive_partitioning=true) v
                WHERE v.cd_cargo = ?
                  {filtro_uf}
                ORDER BY instante
            """
            instantes_originais = con.execute(consulta_instantes, parametros).df()["instante"]

            consulta = f"""
                SELECT
                    v.dt_bu_recebido AS instante,
                    concat(d.nm_votavel, ' (', d.nr_votavel, ')') AS candidato,
                    sum(v.qt_votos)::BIGINT AS votos_no_lote
                FROM read_parquet('{caminho_fatos}', hive_partitioning=true) v
                JOIN read_parquet('{caminho_dim}') d USING (id_votavel)
                WHERE v.cd_cargo = ?
                  AND d.cd_tipo_votavel = 1
                  {filtro_uf}
                GROUP BY instante, candidato
                ORDER BY instante, candidato
            """

            lotes = con.execute(consulta, parametros).df()
            if lotes.empty:
                raise ValueError("A seleção não retornou votos. Revise CARGO e UF.")

            incrementos = (
                lotes.pivot_table(index="instante", columns="candidato", values="votos_no_lote", aggfunc="sum")
                .fillna(0)
                .sort_index()
            )
            incrementos = incrementos.reindex(pd.DatetimeIndex(instantes_originais), fill_value=0)
            incrementos.index.name = "instante"
            acumulado = incrementos.cumsum()
            participacao = acumulado.div(acumulado.sum(axis=1), axis=0).mul(100).fillna(0)
            variacao_percentual = participacao.diff().fillna(0)
            ordem_atualizacao = pd.RangeIndex(1, len(incrementos) + 1, name="atualizacao")
            horarios_texto = incrementos.index.strftime("%d/%m/%Y %H:%M:%S")

            print(f"Período: {acumulado.index.min()} a {acumulado.index.max()}")
            print(f"Atualizações reproduzidas em ordem: {len(acumulado):,}")
            print(f"Candidatos: {', '.join(acumulado.columns)}")
            '''
        ),
        markdown(
            """
            ## Validação da série

            A célula abaixo confere novamente o total diretamente no fato e garante que nenhuma
            linha acumulada diminua. Se houver divergência, a execução para com erro.
            """
        ),
        code(
            '''
            consulta_total = f"""
                SELECT sum(v.qt_votos)::BIGINT
                FROM read_parquet('{caminho_fatos}', hive_partitioning=true) v
                JOIN read_parquet('{caminho_dim}') d USING (id_votavel)
                WHERE v.cd_cargo = ?
                  AND d.cd_tipo_votavel = 1
                  {filtro_uf}
            """
            total_fato = con.execute(consulta_total, parametros).fetchone()[0]
            total_serie = int(incrementos.to_numpy().sum())
            monotono = bool(acumulado.diff().fillna(acumulado).ge(0).all().all())
            percentuais_fecham = bool(participacao.sum(axis=1).sub(100).abs().lt(1e-9).all())
            ordem_cronologica = bool(incrementos.index.is_monotonic_increasing)
            instantes_unicos = not bool(incrementos.index.has_duplicates)

            assert total_serie == total_fato, f"Divergência: série={total_serie}, fato={total_fato}"
            assert monotono, "Ao menos uma série acumulada diminuiu."
            assert percentuais_fecham, "Os percentuais por atualização não fecham em 100%."
            assert ordem_cronologica, "As atualizações não estão em ordem cronológica."
            assert instantes_unicos, "Existem atualizações duplicadas no eixo sequencial."

            validacao = pd.DataFrame({
                "controle": [
                    "Total da série = total do fato",
                    "Séries acumuladas não diminuem",
                    "Percentuais fecham em 100% a cada atualização",
                    "Atualizações seguem DT_BU_RECEBIDO",
                    "Um ponto por segundo/lote nacional",
                ],
                "resultado": ["OK", "OK", "OK", "OK", "OK"],
                "valor": [
                    f"{total_serie:,}",
                    monotono,
                    percentuais_fecham,
                    ordem_cronologica,
                    instantes_unicos,
                ],
            })
            display(validacao)
            '''
        ),
        markdown("## Resultado final da seleção"),
        code(
            """
            resultado = acumulado.iloc[-1].sort_values(ascending=False).rename("votos").to_frame()
            resultado["percentual_validos"] = resultado["votos"] / resultado["votos"].sum() * 100
            resultado["votos_formatados"] = resultado["votos"].map(lambda x: f"{int(x):,}".replace(",", "."))
            display(resultado[["votos_formatados", "percentual_validos"]])
            """
        ),
        markdown(
            """
            ## Percentual dos votos válidos durante a apuração

            Este é o único gráfico analítico do notebook. O eixo horizontal numera os lotes
            nacionais na ordem crescente de `DT_BU_RECEBIDO`, sem intervalos artificiais.

            - **Isolar uma linha:** dê duplo clique no nome do candidato na legenda. Um clique
              simples apenas oculta ou exibe a linha.
            - **Zoom em qualquer região:** com a lupa selecionada, desenhe um retângulo diretamente
              ao redor do trecho da linha. O zoom atua simultaneamente nos eixos X e Y.
            - **Mostrar a variação:** use o botão `Variação por atualização (p.p.)` dentro do
              gráfico. Ele troca o nível acumulado pela mudança do percentual entre dois lotes
              consecutivos. O botão `Percentual acumulado` retorna à visão original.
            - **Restaurar:** dê duplo clique em uma área vazia do gráfico.

            O cursor mostra atualização, horário, porcentagem, variação em pontos percentuais,
            quantidade acumulada e votos recebidos naquele lote.
            """
        ),
        code(
            """
            cores = {"LULA (13)": "#D62728", "JAIR BOLSONARO (22)": "#1F77B4"}
            local = "Brasil" if UF is None else UF.upper()
            candidatos = list(participacao.columns)
            fig = go.Figure()

            for candidato in candidatos:
                detalhes = pd.concat(
                    [acumulado[candidato], incrementos[candidato], variacao_percentual[candidato]],
                    axis=1,
                ).to_numpy()
                fig.add_trace(go.Scatter(
                    x=ordem_atualizacao,
                    y=participacao[candidato],
                    text=horarios_texto,
                    customdata=detalhes,
                    name=candidato,
                    mode="lines+markers",
                    line={"width": 2.3, "color": cores.get(candidato), "shape": "hv"},
                    marker={"size": 3, "color": cores.get(candidato)},
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Atualização: %{x:,.0f}<br>"
                        "Horário: %{text}<br>"
                        "Percentual dos válidos: %{y:.6f}%<br>"
                        "Variação desde o lote anterior: %{customdata[2]:+.6f} p.p.<br>"
                        "Quantidade acumulada: %{customdata[0]:,.0f} votos<br>"
                        "Votos neste lote: +%{customdata[1]:,.0f}"
                        "<extra></extra>"
                    ),
                ))

            for candidato in candidatos:
                detalhes = pd.concat(
                    [participacao[candidato], acumulado[candidato], incrementos[candidato]],
                    axis=1,
                ).to_numpy()
                fig.add_trace(go.Scatter(
                    x=ordem_atualizacao,
                    y=variacao_percentual[candidato],
                    text=horarios_texto,
                    customdata=detalhes,
                    name=candidato,
                    mode="lines+markers",
                    visible=False,
                    line={"width": 1.5, "color": cores.get(candidato)},
                    marker={"size": 3, "color": cores.get(candidato)},
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Atualização: %{x:,.0f}<br>"
                        "Horário: %{text}<br>"
                        "Variação: %{y:+.6f} p.p.<br>"
                        "Percentual após o lote: %{customdata[0]:.6f}%<br>"
                        "Quantidade acumulada: %{customdata[1]:,.0f} votos<br>"
                        "Votos neste lote: +%{customdata[2]:,.0f}"
                        "<extra></extra>"
                    ),
                ))

            quantidade_candidatos = len(candidatos)
            visibilidade_percentual = [True] * quantidade_candidatos + [False] * quantidade_candidatos
            visibilidade_variacao = [False] * quantidade_candidatos + [True] * quantidade_candidatos

            configurar_replay(
                fig,
                f"Percentual dos votos válidos durante a apuração — {local}",
                "Participação nos votos válidos (%)",
            )
            fig.update_yaxes(ticksuffix="%", rangemode="normal")
            fig.update_layout(
                updatemenus=[{
                    "type": "buttons",
                    "direction": "right",
                    "x": 0,
                    "y": 1.20,
                    "showactive": True,
                    "buttons": [
                        {
                            "label": "Percentual acumulado",
                            "method": "update",
                            "args": [
                                {"visible": visibilidade_percentual},
                                {
                                    "title.text": f"Percentual dos votos válidos durante a apuração — {local}",
                                    "yaxis.title.text": "Participação nos votos válidos (%)",
                                    "yaxis.ticksuffix": "%",
                                    "yaxis.autorange": True,
                                    "yaxis.zeroline": False,
                                },
                            ],
                        },
                        {
                            "label": "Variação por atualização (p.p.)",
                            "method": "update",
                            "args": [
                                {"visible": visibilidade_variacao},
                                {
                                    "title.text": f"Variação do percentual a cada atualização — {local}",
                                    "yaxis.title.text": "Variação desde o lote anterior (p.p.)",
                                    "yaxis.ticksuffix": " p.p.",
                                    "yaxis.autorange": True,
                                    "yaxis.zeroline": True,
                                },
                            ],
                        },
                    ],
                }],
            )
            fig.show(config=CONFIG_GRAFICO)
            """
        ),
        markdown("## Síntese automática"),
        code(
            """
            lider_por_instante = acumulado.idxmax(axis=1)
            trocas_lideranca = int(lider_por_instante.ne(lider_por_instante.shift()).sum() - 1)
            lider_final = resultado.index[0]
            margem_final = int(resultado.iloc[0, 0] - resultado.iloc[1, 0]) if len(resultado) > 1 else 0
            picos = pd.DataFrame({
                "horário_da_atualização": incrementos.idxmax(),
                "votos_adicionados": incrementos.max().astype("int64"),
            })

            print(f"Líder ao final da seleção: {lider_final}")
            print(f"Margem final entre os dois primeiros: {margem_final:,} votos".replace(",", "."))
            print(f"Trocas de liderança observadas entre atualizações: {trocas_lideranca}")
            print("\\nAtualização de maior entrada de votos por candidato:")
            display(picos)
            con.close()
            """
        ),
        markdown(
            """
            ## Limitações

            - A fonte informa recebimento com precisão de segundos, mas não uma sequência interna
              para boletins com o mesmo horário.
            - Neste notebook, uma atualização é cada valor distinto de `DT_BU_RECEBIDO`. Os
              arquivos de boletim não registram as chamadas ou atualizações visuais do painel
              público do TSE.
            - Existem alertas temporais documentados em `04_bi/auditoria/alertas_temporais.csv`.
            - O notebook preserva os horários informados e não tenta corrigi-los por fuso ou por
              comparação com `DT_EMISSAO_BU`.
            """
        ),
    ]

    nbf.write(notebook, NOTEBOOK_PATH)
    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    client.execute()
    nbf.write(notebook, NOTEBOOK_PATH)
    print(f"Notebook gerado e executado: {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
