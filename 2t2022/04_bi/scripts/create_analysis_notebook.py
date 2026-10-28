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
                "toImageButtonOptions": {"format": "png", "scale": 2},
            }

            def configurar_tempo(figura, titulo, eixo_y):
                figura.update_layout(
                    title={"text": titulo, "x": 0.02, "xanchor": "left"},
                    height=650,
                    template="plotly_white",
                    hovermode="x unified",
                    dragmode="zoom",
                    legend={"title": {"text": "Candidato"}, "orientation": "h", "y": 1.08},
                    margin={"l": 75, "r": 35, "t": 105, "b": 85},
                    xaxis={
                        "title": "Recebimento do boletim de urna",
                        "type": "date",
                        "rangeslider": {"visible": True, "thickness": 0.10},
                        "rangeselector": {
                            "buttons": [
                                {"count": 15, "label": "15 min", "step": "minute", "stepmode": "backward"},
                                {"count": 1, "label": "1 h", "step": "hour", "stepmode": "backward"},
                                {"count": 6, "label": "6 h", "step": "hour", "stepmode": "backward"},
                                {"step": "all", "label": "Tudo"},
                            ],
                            "x": 0,
                            "y": 1.16,
                        },
                        "showspikes": True,
                        "spikemode": "across",
                    },
                    yaxis={"title": eixo_y, "rangemode": "tozero", "separatethousands": True},
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
            incrementos.index.name = "instante"
            acumulado = incrementos.cumsum()

            print(f"Período: {acumulado.index.min()} a {acumulado.index.max()}")
            print(f"Atualizações distintas no segundo: {len(acumulado):,}")
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

            assert total_serie == total_fato, f"Divergência: série={total_serie}, fato={total_fato}"
            assert monotono, "Ao menos uma série acumulada diminuiu."

            validacao = pd.DataFrame({
                "controle": ["Total da série = total do fato", "Séries acumuladas não diminuem"],
                "resultado": ["OK", "OK"],
                "valor": [f"{total_serie:,}", monotono],
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
            ## Votos acumulados

            Cada linha representa um candidato. O eixo horizontal segue a data/hora de recebimento
            dos boletins; o eixo vertical mostra votos nominais acumulados.

            A linha em degraus muda em cada horário de recebimento disponível na fonte. Passe o
            cursor sobre um degrau para ver a data, a hora com segundos e o total naquele ponto.

            **Zoom interativo:** arraste sobre qualquer trecho para ampliar; use a roda do mouse
            sobre o gráfico; mova as alças da faixa inferior; ou use os botões `15 min`, `1 h`,
            `6 h` e `Tudo`. A barra no canto superior direito permite alternar entre zoom e
            deslocamento. Um duplo clique restaura a visão completa.
            """
        ),
        code(
            """
            cores = {"LULA (13)": "#D62728", "JAIR BOLSONARO (22)": "#1F77B4"}
            local = "Brasil" if UF is None else UF.upper()
            fig = go.Figure()
            for candidato in acumulado.columns:
                fig.add_trace(go.Scatter(
                    x=acumulado.index,
                    y=acumulado[candidato],
                    name=candidato,
                    mode="lines+markers",
                    line={"width": 2.2, "color": cores.get(candidato), "shape": "hv"},
                    marker={"size": 3, "color": cores.get(candidato)},
                    hovertemplate="%{x|%d/%m/%Y %H:%M:%S}<br>%{fullData.name}: %{y:,.0f} votos<extra></extra>",
                ))

            configurar_tempo(
                fig,
                f"Evolução dos votos acumulados — {local}",
                "Votos nominais acumulados",
            )
            fig.update_yaxes(tickformat=",.0f")
            fig.show(config=CONFIG_GRAFICO)
            """
        ),
        markdown(
            """
            ## Participação nos votos válidos ao longo da apuração

            Este gráfico usa apenas os candidatos selecionados; branco e nulo não entram no
            denominador. Oscilações no início refletem poucos boletins recebidos. Os mesmos
            controles de zoom do gráfico anterior estão disponíveis aqui.
            """
        ),
        code(
            """
            participacao = acumulado.div(acumulado.sum(axis=1), axis=0).mul(100).fillna(0)
            fig = go.Figure()
            for candidato in participacao.columns:
                fig.add_trace(go.Scatter(
                    x=participacao.index,
                    y=participacao[candidato],
                    name=candidato,
                    mode="lines",
                    line={"width": 2.2, "color": cores.get(candidato), "shape": "hv"},
                    hovertemplate="%{x|%d/%m/%Y %H:%M:%S}<br>%{fullData.name}: %{y:.4f}%<extra></extra>",
                ))

            configurar_tempo(
                fig,
                f"Percentual dos votos válidos durante a apuração — {local}",
                "Participação nos votos válidos (%)",
            )
            fig.update_yaxes(ticksuffix="%", rangemode="normal")
            fig.show(config=CONFIG_GRAFICO)
            """
        ),
        markdown(
            """
            ## Variação a cada atualização

            Este gráfico mostra quantos votos de cada candidato entraram em cada horário distinto
            de recebimento, sem agrupar por minuto ou por intervalos de 15 minutos. Use o zoom para
            separar os pontos que ficam sobrepostos quando todo o período está visível.
            """
        ),
        code(
            """
            fig = go.Figure()
            for candidato in incrementos.columns:
                fig.add_trace(go.Scatter(
                    x=incrementos.index,
                    y=incrementos[candidato],
                    name=candidato,
                    mode="lines+markers",
                    line={"width": 1.2, "color": cores.get(candidato)},
                    marker={"size": 3, "color": cores.get(candidato)},
                    hovertemplate="%{x|%d/%m/%Y %H:%M:%S}<br>%{fullData.name}: +%{y:,.0f} votos<extra></extra>",
                ))

            configurar_tempo(
                fig,
                f"Votos adicionados em cada atualização — {local}",
                "Votos adicionados na atualização",
            )
            fig.update_yaxes(tickformat=",.0f")
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
