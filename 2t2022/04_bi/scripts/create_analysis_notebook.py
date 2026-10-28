#!/usr/bin/env python3
"""Gera e executa o notebook da evolução oficial da totalização."""

from __future__ import annotations

import hashlib
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
            # Evolução oficial da totalização presidencial

            Este notebook reproduz as atualizações da totalização para Presidente no Brasil,
            no segundo turno de 2022, e compara dois relógios diferentes:

            1. `DT_BU_RECEBIDO`: horário de recebimento informado na fonte do BU;
            2. `DT_TOTALIZACAO`: horário de uma atualização do histórico oficial.

            Cada ponto corresponde a uma linha de `DT_TOTALIZACAO`. Os valores de cada
            atualização e os acumulados vêm diretamente do histórico, sem reconstrução por
            `DT_BU_RECEBIDO`, agrupamento por período ou reamostragem. Os boletins de urna são
            usados separadamente para conferir os totais finais e medir a relação temporal
            entre recebimento e totalização.
            """
        ),
        code(
            '''
            import hashlib
            from pathlib import Path

            import duckdb
            import matplotlib.pyplot as plt
            import numpy as np
            import pandas as pd
            import plotly.graph_objects as go
            import plotly.io as pio
            from IPython.display import Markdown, display
            from matplotlib.ticker import PercentFormatter

            pio.renderers.default = "plotly_mimetype"
            plt.rcParams.update({
                "font.family": "DejaVu Sans",
                "svg.fonttype": "none",
                "svg.hashsalt": "apuracoes-2t2022",
            })

            NOME_ARQUIVO_HISTORICO = "Historico_Totalizacao_Presidente_BR_2T_2022.csv"
            SHA256_HISTORICO_ESPERADO = (
                "00013c958f13b2cf1a842c4398ca7cb52cf5ef46d26ce91f99c1a0ad8d0f663d"
            )

            def sha256_arquivo(caminho: Path) -> str:
                resumo = hashlib.sha256()
                with caminho.open("rb") as arquivo:
                    for bloco in iter(lambda: arquivo.read(8 * 1024 * 1024), b""):
                        resumo.update(bloco)
                return resumo.hexdigest()

            def localizar_raiz_2t2022(inicio: Path) -> Path:
                inicio = inicio.resolve()
                for pasta in (inicio, *inicio.parents):
                    if (pasta / "04_bi" / "dados" / "fato_votos").exists():
                        return pasta
                    candidato = pasta / "2t2022"
                    if (candidato / "04_bi" / "dados" / "fato_votos").exists():
                        return candidato
                raise FileNotFoundError("Não foi possível localizar 2t2022/04_bi/dados/fato_votos")

            RAIZ_2T2022 = localizar_raiz_2t2022(Path.cwd())
            PASTA_GRAFICOS = RAIZ_2T2022 / "04_bi" / "graficos"
            PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)
            HISTORICO = (
                RAIZ_2T2022 / "04_bi" / "fontes" / "historico_totalizacao"
                / NOME_ARQUIVO_HISTORICO
            )
            if not HISTORICO.exists():
                raise FileNotFoundError(f"Fonte do histórico não encontrada: {HISTORICO}")
            sha256_historico = sha256_arquivo(HISTORICO)
            assert sha256_historico == SHA256_HISTORICO_ESPERADO, {
                "esperado": SHA256_HISTORICO_ESPERADO,
                "obtido": sha256_historico,
            }
            FATOS_VOTOS = RAIZ_2T2022 / "04_bi" / "dados" / "fato_votos" / "**" / "*.parquet"
            FATOS_BOLETINS = (
                RAIZ_2T2022 / "04_bi" / "dados" / "fato_boletins" / "**" / "*.parquet"
            )

            def salvar_figura_svg(figura, nome_arquivo):
                destino = PASTA_GRAFICOS / nome_arquivo
                temporario = destino.with_name(destino.name + ".part")
                figura.savefig(
                    temporario,
                    format="svg",
                    bbox_inches="tight",
                    metadata={"Date": None, "Creator": "Apurações 2T 2022"},
                )
                svg_normalizado = "\\n".join(
                    linha.rstrip()
                    for linha in temporario.read_text(encoding="utf-8").splitlines()
                ) + "\\n"
                temporario.write_text(svg_normalizado, encoding="utf-8")
                temporario.replace(destino)
                plt.close(figura)

            pd.set_option("display.max_rows", 20)
            pd.set_option("display.float_format", lambda valor: f"{valor:,.6f}")

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
                    height=680,
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
                    margin={"l": 75, "r": 35, "t": 145, "b": 70},
                    xaxis={
                        "title": "Ordem oficial das atualizações",
                        "type": "linear",
                        "tickformat": ",d",
                        "showspikes": True,
                        "spikemode": "across",
                        "spikesnap": "data",
                    },
                    yaxis={
                        "title": eixo_y,
                        "separatethousands": True,
                        "showspikes": True,
                        "spikemode": "across",
                        "spikesnap": "data",
                    },
                )
                return figura

            print(f"Histórico oficial: {HISTORICO.relative_to(RAIZ_2T2022)}")
            print(f"SHA-256 validado: {sha256_historico}")
            print("Votos dos BUs: 04_bi/dados/fato_votos/**/*.parquet")
            print("Metadados dos BUs: 04_bi/dados/fato_boletins/**/*.parquet")
            '''
        ),
        markdown("## Leitura e normalização do histórico oficial"),
        code(
            '''
            dados = pd.read_csv(
                HISTORICO,
                sep=";",
                encoding="latin-1",
                decimal=",",
                skipinitialspace=True,
            )
            dados.columns = dados.columns.str.strip()
            dados["SG_UE_UF"] = dados["SG_UE_UF"].astype(str).str.strip()
            dados["DT_TOTALIZACAO"] = pd.to_datetime(
                dados["DT_TOTALIZACAO"].astype(str).str.strip(),
                format="%d/%m/%Y %H:%M:%S",
                errors="raise",
            )

            colunas_numericas = [
                coluna for coluna in dados.columns
                if coluna not in {"SG_UE_UF", "DT_TOTALIZACAO"}
            ]
            for coluna in colunas_numericas:
                dados[coluna] = pd.to_numeric(
                    dados[coluna].astype(str).str.strip().str.replace(",", ".", regex=False),
                    errors="raise",
                )

            dados = dados.sort_values("DT_TOTALIZACAO", kind="stable").reset_index(drop=True)

            candidatos_config = {
                "LULA": "LULA (13)",
                "JAIR_BOLSONARO": "JAIR BOLSONARO (22)",
            }
            indice = pd.DatetimeIndex(dados["DT_TOTALIZACAO"], name="instante")
            incrementos = pd.DataFrame({
                rotulo: dados[f"{prefixo}_QT_VOTOS_TOT"].astype("int64").to_numpy()
                for prefixo, rotulo in candidatos_config.items()
            }, index=indice)
            acumulado = pd.DataFrame({
                rotulo: dados[f"{prefixo}_QT_VOTOS_TOT_ACUMULADO"].astype("int64").to_numpy()
                for prefixo, rotulo in candidatos_config.items()
            }, index=indice)
            participacao = pd.DataFrame({
                rotulo: dados[f"{prefixo}_PE_VOTOS_TOT_ACUMULADO"].mul(100).to_numpy()
                for prefixo, rotulo in candidatos_config.items()
            }, index=indice)
            variacao_percentual = participacao.diff().fillna(0)

            ordem_atualizacao = pd.RangeIndex(1, len(dados) + 1, name="atualizacao")
            horarios_texto = indice.strftime("%d/%m/%Y %H:%M:%S")
            votos_validos_no_incremento = dados["QT_VOTOS_CONCORRENTES"].astype("int64")
            secoes_no_incremento = dados["QT_SECOES_TOT"].astype("int64")
            secoes_acumuladas = dados["QT_SECOES_TOT_ACUMULADO"].astype("int64")
            percentual_secoes = dados["PE_SECOES_TOT_ACUMULADO"].mul(100)

            print(f"Período oficial: {indice.min()} a {indice.max()}")
            print(f"Atualizações oficiais: {len(dados):,}")
            print(f"Candidatos: {', '.join(acumulado.columns)}")
            '''
        ),
        markdown(
            """
            ## Validação independente

            Primeiro são verificadas as relações internas documentadas no leia-me: incremento,
            acumulado, votos válidos, percentuais, ordem e unicidade. Depois, os totais finais
            do histórico são comparados com a soma dos BUs divulgados. A execução para se houver
            qualquer divergência de votos.
            """
        ),
        code(
            '''
            acumulado_recalculado = incrementos.cumsum()
            incrementos_recalculados = acumulado.diff()
            incrementos_recalculados.iloc[0] = acumulado.iloc[0]

            metadados_corretos = bool(
                dados["CD_PLEITO"].eq(407).all()
                and dados["CD_ELEICAO"].eq(545).all()
                and dados["CD_CARGO"].eq(1).all()
                and dados["SG_UE_UF"].eq("BR").all()
            )
            sem_nulos = not bool(dados.isna().any().any())
            ordem_cronologica = bool(indice.is_monotonic_increasing)
            instantes_unicos = not bool(indice.has_duplicates)
            incrementos_fecham = bool(incrementos_recalculados.astype("int64").equals(incrementos))
            acumulados_fecham = bool(acumulado_recalculado.equals(acumulado))
            validos_fecham = bool(
                incrementos.sum(axis=1).reset_index(drop=True).eq(votos_validos_no_incremento).all()
                and acumulado.sum(axis=1).reset_index(drop=True).eq(
                    dados["QT_VOTOS_CONCORRENTES_ACUMULADO"].astype("int64")
                ).all()
            )
            percentual_recalculado = acumulado.div(acumulado.sum(axis=1), axis=0).mul(100)
            percentuais_fecham = bool(np.allclose(
                participacao.to_numpy(),
                percentual_recalculado.to_numpy(),
                rtol=0,
                atol=0.000051,
            ))

            controles_internos = {
                "Metadados identificam Presidente/BR/2T2022": metadados_corretos,
                "Nenhum valor ausente": sem_nulos,
                "DT_TOTALIZACAO crescente": ordem_cronologica,
                "Um ponto por DT_TOTALIZACAO": instantes_unicos,
                "Incrementos = diferença dos acumulados": incrementos_fecham,
                "Acumulados = soma dos incrementos": acumulados_fecham,
                "Votos dos candidatos = votos válidos": validos_fecham,
                "Percentuais oficiais reproduzem a fórmula": percentuais_fecham,
            }
            assert all(controles_internos.values()), controles_internos

            caminho_fatos = str(FATOS_VOTOS).replace("'", "''")
            con = duckdb.connect()
            totais_bu = dict(con.execute(f"""
                SELECT nr_votavel, sum(qt_votos)::BIGINT AS votos
                FROM read_parquet('{caminho_fatos}', hive_partitioning=true)
                WHERE cd_cargo = 1
                GROUP BY nr_votavel
            """).fetchall())

            final_historico_por_numero = {
                13: int(dados.iloc[-1]["LULA_QT_VOTOS_TOT_ACUMULADO"]),
                22: int(dados.iloc[-1]["JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO"]),
                95: int(dados.iloc[-1]["BRANCO_QT_VOTOS_TOT_ACUMULADO"]),
                96: int(dados.iloc[-1]["NULO_QT_VOTOS_TOT_ACUMULADO"]),
            }
            comparacao_bu = pd.DataFrame([
                {
                    "tipo": {13: "LULA", 22: "JAIR BOLSONARO", 95: "Branco", 96: "Nulo"}[numero],
                    "número": numero,
                    "histórico": total,
                    "soma_dos_BUs": int(totais_bu.get(numero, -1)),
                    "diferença": total - int(totais_bu.get(numero, -1)),
                }
                for numero, total in final_historico_por_numero.items()
            ])
            assert comparacao_bu["diferença"].eq(0).all(), comparacao_bu

            validacao = pd.DataFrame({
                "controle": list(controles_internos),
                "resultado": ["OK" if valor else "FALHA" for valor in controles_internos.values()],
            })
            display(validacao)
            comparacao_exibicao = comparacao_bu.copy()
            for coluna in ["histórico", "soma_dos_BUs"]:
                comparacao_exibicao[coluna] = comparacao_exibicao[coluna].map(
                    lambda valor: f"{int(valor):,}".replace(",", ".")
                )
            comparacao_exibicao["diferença"] = comparacao_exibicao["diferença"].map(
                lambda valor: f"{int(valor):+d}"
            )
            display(comparacao_exibicao)
            '''
        ),
        markdown("## Resultado final"),
        code(
            '''
            resultado = acumulado.iloc[-1].sort_values(ascending=False).rename("votos").to_frame()
            resultado["percentual_validos"] = participacao.iloc[-1].reindex(resultado.index)
            resultado["votos_formatados"] = resultado["votos"].map(
                lambda valor: f"{int(valor):,}".replace(",", ".")
            )
            display(resultado[["votos_formatados", "percentual_validos"]])
            '''
        ),
        code(
            '''
            # Delimitação observável usada apenas para colorir o gráfico principal.
            # O histórico não publica o identificador interno dos lotes.
            LIMIAR_PAUSA_SEGUNDOS = 10
            intervalos_atualizacao = dados["DT_TOTALIZACAO"].diff().dt.total_seconds()
            intervalos_positivos = intervalos_atualizacao.dropna()
            assert not intervalos_positivos.between(10, 12).any()

            tabela_distribuicao_intervalos = pd.DataFrame({
                "Intervalo": [
                    "1–3 segundos",
                    "4–6 segundos",
                    "7–9 segundos",
                    "10–12 segundos",
                    "13–19 segundos",
                    "20 segundos ou mais",
                ],
                "Ocorrências": [
                    int(intervalos_positivos.between(1, 3).sum()),
                    int(intervalos_positivos.between(4, 6).sum()),
                    int(intervalos_positivos.between(7, 9).sum()),
                    int(intervalos_positivos.between(10, 12).sum()),
                    int(intervalos_positivos.between(13, 19).sum()),
                    int(intervalos_positivos.ge(20).sum()),
                ],
            })
            assert tabela_distribuicao_intervalos["Ocorrências"].tolist() == [
                4934, 66, 9, 0, 25, 251,
            ]
            assert int(tabela_distribuicao_intervalos["Ocorrências"].sum()) == len(
                intervalos_positivos
            )

            dados_blocos = dados.copy()
            dados_blocos["ORDEM_ATUALIZACAO"] = np.arange(1, len(dados_blocos) + 1)
            dados_blocos["BLOCO_OBSERVADO"] = (
                intervalos_atualizacao.ge(LIMIAR_PAUSA_SEGUNDOS).cumsum().add(1).astype("int64")
            )
            dados_blocos["POSICAO_NO_BLOCO"] = (
                dados_blocos.groupby("BLOCO_OBSERVADO").cumcount().add(1)
            )

            blocos_observados = (
                dados_blocos.groupby("BLOCO_OBSERVADO", sort=True)
                .agg(
                    inicio_totalizacao=("DT_TOTALIZACAO", "min"),
                    fim_totalizacao=("DT_TOTALIZACAO", "max"),
                    primeira_atualizacao=("ORDEM_ATUALIZACAO", "min"),
                    ultima_atualizacao=("ORDEM_ATUALIZACAO", "max"),
                    quantidade_atualizacoes=("DT_TOTALIZACAO", "size"),
                    secoes_incorporadas=("QT_SECOES_TOT", "sum"),
                    votos_validos_incorporados=("QT_VOTOS_CONCORRENTES", "sum"),
                    votos_lula=("LULA_QT_VOTOS_TOT", "sum"),
                    votos_bolsonaro=("JAIR_BOLSONARO_QT_VOTOS_TOT", "sum"),
                    bolsonaro_percentual_depois=(
                        "JAIR_BOLSONARO_PE_VOTOS_TOT_ACUMULADO", "last"
                    ),
                )
                .reset_index()
            )
            blocos_observados["duracao_segundos"] = (
                blocos_observados["fim_totalizacao"]
                - blocos_observados["inicio_totalizacao"]
            ).dt.total_seconds().astype("int64")
            blocos_observados["intervalo_entre_inicios_segundos"] = (
                blocos_observados["inicio_totalizacao"].diff().dt.total_seconds()
            )
            blocos_observados["lula_percentual_no_bloco"] = (
                blocos_observados["votos_lula"]
                .div(blocos_observados["votos_validos_incorporados"])
                .mul(100)
            )
            blocos_observados["bolsonaro_percentual_no_bloco"] = (
                blocos_observados["votos_bolsonaro"]
                .div(blocos_observados["votos_validos_incorporados"])
                .mul(100)
            )
            blocos_observados["bolsonaro_percentual_depois"] *= 100
            blocos_observados["bolsonaro_percentual_antes"] = (
                blocos_observados["bolsonaro_percentual_depois"].shift(1)
            )
            blocos_observados["variacao_bolsonaro_pp"] = (
                blocos_observados["bolsonaro_percentual_depois"]
                - blocos_observados["bolsonaro_percentual_antes"]
            )
            colunas_percentuais_blocos = [
                "lula_percentual_no_bloco",
                "bolsonaro_percentual_no_bloco",
                "bolsonaro_percentual_antes",
                "bolsonaro_percentual_depois",
                "variacao_bolsonaro_pp",
            ]
            blocos_observados[colunas_percentuais_blocos] = blocos_observados[
                colunas_percentuais_blocos
            ].round(6)
            blocos_observados["intervalo_entre_inicios_segundos"] = blocos_observados[
                "intervalo_entre_inicios_segundos"
            ].astype("Int64")
            blocos_observados["direcao_bolsonaro"] = np.select(
                [
                    blocos_observados["variacao_bolsonaro_pp"].gt(0),
                    blocos_observados["variacao_bolsonaro_pp"].lt(0),
                ],
                ["subiu", "caiu"],
                default="sem mudança",
            )
            blocos_observados.loc[0, "direcao_bolsonaro"] = "início da série"

            intervalos_entre_blocos = blocos_observados[
                "intervalo_entre_inicios_segundos"
            ].dropna()
            quantidade_blocos = len(blocos_observados)
            mediana_intervalo_blocos = float(intervalos_entre_blocos.median())
            blocos_entre_55_e_70 = int(intervalos_entre_blocos.between(55, 70).sum())
            percentual_blocos_entre_55_e_70 = (
                blocos_entre_55_e_70 / len(intervalos_entre_blocos) * 100
            )
            assert quantidade_blocos == 277
            assert mediana_intervalo_blocos == 65
            assert blocos_entre_55_e_70 == 253
            assert int(blocos_observados["quantidade_atualizacoes"].sum()) == len(dados)
            assert int(blocos_observados["secoes_incorporadas"].sum()) == int(
                dados.iloc[-1]["QT_SECOES_TOT_ACUMULADO"]
            )
            assert int(blocos_observados["votos_validos_incorporados"].sum()) == int(
                dados.iloc[-1]["QT_VOTOS_CONCORRENTES_ACUMULADO"]
            )
            assert int(blocos_observados["votos_lula"].sum()) == int(
                dados.iloc[-1]["LULA_QT_VOTOS_TOT_ACUMULADO"]
            )
            assert int(blocos_observados["votos_bolsonaro"].sum()) == int(
                dados.iloc[-1]["JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO"]
            )

            caminho_tabela_blocos = (
                RAIZ_2T2022 / "04_bi" / "auditoria" / "blocos_totalizacao.csv"
            )
            colunas_tabela_blocos = [
                "BLOCO_OBSERVADO",
                "inicio_totalizacao",
                "fim_totalizacao",
                "duracao_segundos",
                "intervalo_entre_inicios_segundos",
                "primeira_atualizacao",
                "ultima_atualizacao",
                "quantidade_atualizacoes",
                "secoes_incorporadas",
                "votos_validos_incorporados",
                "votos_lula",
                "votos_bolsonaro",
                "lula_percentual_no_bloco",
                "bolsonaro_percentual_no_bloco",
                "bolsonaro_percentual_antes",
                "bolsonaro_percentual_depois",
                "variacao_bolsonaro_pp",
                "direcao_bolsonaro",
            ]
            caminho_tabela_blocos_temporario = caminho_tabela_blocos.with_name(
                caminho_tabela_blocos.name + ".part"
            )
            blocos_observados[colunas_tabela_blocos].to_csv(
                caminho_tabela_blocos_temporario,
                sep=";",
                decimal=",",
                index=False,
                encoding="utf-8",
                date_format="%Y-%m-%d %H:%M:%S",
            )
            caminho_tabela_blocos_temporario.replace(caminho_tabela_blocos)

            metadados_blocos = blocos_observados[[
                "BLOCO_OBSERVADO",
                "inicio_totalizacao",
                "fim_totalizacao",
                "quantidade_atualizacoes",
                "secoes_incorporadas",
                "votos_validos_incorporados",
                "lula_percentual_no_bloco",
                "bolsonaro_percentual_no_bloco",
                "variacao_bolsonaro_pp",
                "direcao_bolsonaro",
            ]]
            dados_blocos = dados_blocos.merge(
                metadados_blocos,
                on="BLOCO_OBSERVADO",
                how="left",
                validate="many_to_one",
            )
            dados_blocos["INICIO_BLOCO_TEXTO"] = dados_blocos[
                "inicio_totalizacao"
            ].dt.strftime("%d/%m/%Y %H:%M:%S")
            dados_blocos["FIM_BLOCO_TEXTO"] = dados_blocos[
                "fim_totalizacao"
            ].dt.strftime("%d/%m/%Y %H:%M:%S")
            '''
        ),
        markdown(
            """
            ## Evolução do percentual e variação por atualização

            Este é o gráfico principal. O eixo horizontal conserva todas as 5.286 atualizações
            na ordem oficial de `DT_TOTALIZACAO`; o horário original aparece ao passar o mouse.

            - **Isolar uma linha:** duplo clique no candidato na legenda.
            - **Zoom livre:** selecione a lupa e desenhe um retângulo em qualquer trecho da linha.
            - **Ver a variação:** use `Variação por atualização (p.p.)` no topo do gráfico.
            - **Restaurar:** duplo clique em uma área vazia.
            - **Identificar blocos:** as faixas claras alternadas ao fundo delimitam os 277
              blocos observados, sem modificar nenhum ponto das linhas.

            O cursor mostra horário, percentual, variação, votos acumulados, votos adicionados,
            votos válidos do incremento, quantidade de seções e início/fim do bloco correspondente.
            """
        ),
        code(
            '''
            cores = {"LULA (13)": "#D62728", "JAIR BOLSONARO (22)": "#1F77B4"}
            candidatos = list(participacao.columns)
            fig = go.Figure()

            dados_comuns = pd.DataFrame({
                "validos_incremento": votos_validos_no_incremento.to_numpy(),
                "secoes_incremento": secoes_no_incremento.to_numpy(),
                "secoes_acumuladas": secoes_acumuladas.to_numpy(),
                "percentual_secoes": percentual_secoes.to_numpy(),
                "bloco": dados_blocos["BLOCO_OBSERVADO"].to_numpy(),
                "posicao_no_bloco": dados_blocos["POSICAO_NO_BLOCO"].to_numpy(),
                "atualizacoes_no_bloco": dados_blocos[
                    "quantidade_atualizacoes"
                ].to_numpy(),
                "inicio_bloco": dados_blocos["INICIO_BLOCO_TEXTO"].to_numpy(),
                "fim_bloco": dados_blocos["FIM_BLOCO_TEXTO"].to_numpy(),
                "secoes_no_bloco": dados_blocos["secoes_incorporadas"].to_numpy(),
                "validos_no_bloco": dados_blocos[
                    "votos_validos_incorporados"
                ].to_numpy(),
                "lula_pct_bloco": dados_blocos["lula_percentual_no_bloco"].to_numpy(),
                "bolsonaro_pct_bloco": dados_blocos[
                    "bolsonaro_percentual_no_bloco"
                ].to_numpy(),
                "efeito_bolsonaro_bloco": dados_blocos[
                    "variacao_bolsonaro_pp"
                ].to_numpy(),
            }, index=indice)

            for candidato in candidatos:
                detalhes = pd.DataFrame({
                    "acumulado": acumulado[candidato].to_numpy(),
                    "incremento": incrementos[candidato].to_numpy(),
                    "variacao": variacao_percentual[candidato].to_numpy(),
                    "validos_incremento": dados_comuns["validos_incremento"].to_numpy(),
                    "secoes_incremento": dados_comuns["secoes_incremento"].to_numpy(),
                    "secoes_acumuladas": dados_comuns["secoes_acumuladas"].to_numpy(),
                    "percentual_secoes": dados_comuns["percentual_secoes"].to_numpy(),
                    "bloco": dados_comuns["bloco"].to_numpy(),
                    "posicao_no_bloco": dados_comuns["posicao_no_bloco"].to_numpy(),
                    "atualizacoes_no_bloco": dados_comuns[
                        "atualizacoes_no_bloco"
                    ].to_numpy(),
                    "inicio_bloco": dados_comuns["inicio_bloco"].to_numpy(),
                    "fim_bloco": dados_comuns["fim_bloco"].to_numpy(),
                    "secoes_no_bloco": dados_comuns["secoes_no_bloco"].to_numpy(),
                    "validos_no_bloco": dados_comuns["validos_no_bloco"].to_numpy(),
                    "lula_pct_bloco": dados_comuns["lula_pct_bloco"].to_numpy(),
                    "bolsonaro_pct_bloco": dados_comuns[
                        "bolsonaro_pct_bloco"
                    ].to_numpy(),
                    "efeito_bolsonaro_bloco": dados_comuns[
                        "efeito_bolsonaro_bloco"
                    ].to_numpy(),
                }).to_numpy(dtype=object)
                fig.add_trace(go.Scatter(
                    x=ordem_atualizacao,
                    y=participacao[candidato],
                    text=horarios_texto,
                    customdata=detalhes,
                    name=candidato,
                    mode="lines+markers",
                    line={"width": 2.3, "color": cores[candidato], "shape": "hv"},
                    marker={"size": 3, "color": cores[candidato]},
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Atualização oficial: %{x:,.0f}<br>"
                        "Horário da totalização: %{text}<br>"
                        "Percentual dos válidos: %{y:.6f}%<br>"
                        "Variação: %{customdata[2]:+.6f} p.p.<br>"
                        "Votos acumulados: %{customdata[0]:,.0f}<br>"
                        "Votos do candidato nesta atualização: +%{customdata[1]:,.0f}<br>"
                        "Votos válidos nesta atualização: %{customdata[3]:,.0f}<br>"
                        "Seções nesta atualização: %{customdata[4]:,.0f}<br>"
                        "Seções acumuladas: %{customdata[5]:,.0f} (%{customdata[6]:.6f}%)<br>"
                        "<br><b>Bloco observado %{customdata[7]:.0f}</b><br>"
                        "Posição no bloco: %{customdata[8]:.0f}/%{customdata[9]:.0f}<br>"
                        "Início: %{customdata[10]}<br>"
                        "Fim: %{customdata[11]}<br>"
                        "Seções no bloco: %{customdata[12]:,.0f}<br>"
                        "Votos válidos no bloco: %{customdata[13]:,.0f}<br>"
                        "Lula no bloco: %{customdata[14]:.6f}%<br>"
                        "Bolsonaro no bloco: %{customdata[15]:.6f}%<br>"
                        "Efeito do bloco em Bolsonaro: %{customdata[16]:+.6f} p.p."
                        "<extra></extra>"
                    ),
                ))

            for candidato in candidatos:
                detalhes = pd.DataFrame({
                    "percentual": participacao[candidato].to_numpy(),
                    "acumulado": acumulado[candidato].to_numpy(),
                    "incremento": incrementos[candidato].to_numpy(),
                    "validos_incremento": dados_comuns["validos_incremento"].to_numpy(),
                    "secoes_incremento": dados_comuns["secoes_incremento"].to_numpy(),
                    "secoes_acumuladas": dados_comuns["secoes_acumuladas"].to_numpy(),
                    "percentual_secoes": dados_comuns["percentual_secoes"].to_numpy(),
                    "bloco": dados_comuns["bloco"].to_numpy(),
                    "posicao_no_bloco": dados_comuns["posicao_no_bloco"].to_numpy(),
                    "atualizacoes_no_bloco": dados_comuns[
                        "atualizacoes_no_bloco"
                    ].to_numpy(),
                    "inicio_bloco": dados_comuns["inicio_bloco"].to_numpy(),
                    "fim_bloco": dados_comuns["fim_bloco"].to_numpy(),
                    "secoes_no_bloco": dados_comuns["secoes_no_bloco"].to_numpy(),
                    "validos_no_bloco": dados_comuns["validos_no_bloco"].to_numpy(),
                    "lula_pct_bloco": dados_comuns["lula_pct_bloco"].to_numpy(),
                    "bolsonaro_pct_bloco": dados_comuns[
                        "bolsonaro_pct_bloco"
                    ].to_numpy(),
                    "efeito_bolsonaro_bloco": dados_comuns[
                        "efeito_bolsonaro_bloco"
                    ].to_numpy(),
                }).to_numpy(dtype=object)
                fig.add_trace(go.Scatter(
                    x=ordem_atualizacao,
                    y=variacao_percentual[candidato],
                    text=horarios_texto,
                    customdata=detalhes,
                    name=candidato,
                    mode="lines+markers",
                    visible=False,
                    line={"width": 1.5, "color": cores[candidato]},
                    marker={"size": 3, "color": cores[candidato]},
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Atualização oficial: %{x:,.0f}<br>"
                        "Horário da totalização: %{text}<br>"
                        "Variação: %{y:+.6f} p.p.<br>"
                        "Percentual após a atualização: %{customdata[0]:.6f}%<br>"
                        "Votos acumulados: %{customdata[1]:,.0f}<br>"
                        "Votos do candidato nesta atualização: +%{customdata[2]:,.0f}<br>"
                        "Votos válidos nesta atualização: %{customdata[3]:,.0f}<br>"
                        "Seções nesta atualização: %{customdata[4]:,.0f}<br>"
                        "Seções acumuladas: %{customdata[5]:,.0f} (%{customdata[6]:.6f}%)<br>"
                        "<br><b>Bloco observado %{customdata[7]:.0f}</b><br>"
                        "Posição no bloco: %{customdata[8]:.0f}/%{customdata[9]:.0f}<br>"
                        "Início: %{customdata[10]}<br>"
                        "Fim: %{customdata[11]}<br>"
                        "Seções no bloco: %{customdata[12]:,.0f}<br>"
                        "Votos válidos no bloco: %{customdata[13]:,.0f}<br>"
                        "Lula no bloco: %{customdata[14]:.6f}%<br>"
                        "Bolsonaro no bloco: %{customdata[15]:.6f}%<br>"
                        "Efeito do bloco em Bolsonaro: %{customdata[16]:+.6f} p.p."
                        "<extra></extra>"
                    ),
                ))

            cores_fundo_blocos = ["#DCEBFA", "#FFF0D6"]
            for linha in blocos_observados.itertuples(index=False):
                fig.add_vrect(
                    x0=linha.primeira_atualizacao - 0.5,
                    x1=linha.ultima_atualizacao + 0.5,
                    fillcolor=cores_fundo_blocos[(linha.BLOCO_OBSERVADO - 1) % 2],
                    opacity=0.32,
                    line_width=0,
                    layer="below",
                )

            quantidade_candidatos = len(candidatos)
            visibilidade_percentual = [True] * quantidade_candidatos + [False] * quantidade_candidatos
            visibilidade_variacao = [False] * quantidade_candidatos + [True] * quantidade_candidatos

            configurar_replay(
                fig,
                "Percentual oficial dos votos válidos durante a totalização — Brasil",
                "Participação nos votos válidos (%)",
            )
            fig.update_yaxes(ticksuffix="%", rangemode="normal")
            fig.update_layout(
                updatemenus=[{
                    "type": "buttons",
                    "direction": "right",
                    "x": 1,
                    "xanchor": "right",
                    "y": 1.21,
                    "showactive": True,
                    "buttons": [
                        {
                            "label": "Percentual acumulado",
                            "method": "update",
                            "args": [
                                {"visible": visibilidade_percentual},
                                {
                                    "title.text": "Percentual oficial dos votos válidos durante a totalização — Brasil",
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
                                    "title.text": "Variação oficial do percentual a cada atualização — Brasil",
                                    "yaxis.title.text": "Variação desde a atualização anterior (p.p.)",
                                    "yaxis.ticksuffix": " p.p.",
                                    "yaxis.autorange": True,
                                    "yaxis.zeroline": True,
                                },
                            ],
                        },
                    ],
                }],
            )

            figura_readme, eixo_readme = plt.subplots(figsize=(13.5, 6.2))
            for linha in blocos_observados.itertuples(index=False):
                eixo_readme.axvspan(
                    linha.primeira_atualizacao - 0.5,
                    linha.ultima_atualizacao + 0.5,
                    color=cores_fundo_blocos[(linha.BLOCO_OBSERVADO - 1) % 2],
                    alpha=0.38,
                    linewidth=0,
                )
            for candidato in candidatos:
                eixo_readme.plot(
                    ordem_atualizacao,
                    participacao[candidato],
                    label=candidato,
                    color=cores[candidato],
                    linewidth=1.4,
                    drawstyle="steps-post",
                )
            eixo_readme.set(
                title="Percentual oficial dos votos válidos durante a totalização — Brasil",
                xlabel="Ordem oficial das 5.286 atualizações",
                ylabel="Participação nos votos válidos",
                xlim=(1, len(dados)),
            )
            eixo_readme.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=1))
            eixo_readme.grid(axis="y", color="#D9E2F2", linewidth=0.8)
            eixo_readme.legend(loc="best", frameon=False, ncol=2)
            figura_readme.tight_layout()
            salvar_figura_svg(figura_readme, "evolucao_percentual_blocos.svg")

            fig.show(config=CONFIG_GRAFICO)
            '''
        ),
        markdown(
            """
            ### Tabela dos blocos marcados no gráfico principal

            O histórico não publica um identificador interno de lote. Por isso, os blocos
            abaixo são **inferidos do ritmo visível da totalização**, sem afirmar quais BUs
            individuais foram selecionados pelo sistema.

            A separação encontrada nos próprios horários é natural: dentro de uma rajada, as
            atualizações consecutivas ficam de 1 a 9 segundos apartadas; não há intervalos de
            10, 11 ou 12 segundos; o próximo intervalo observado começa em 13 segundos. Assim,
            uma pausa de pelo menos 10 segundos inicia um novo **bloco observado**.

            A tabela calculada abaixo mostra todos os 5.285 intervalos consecutivos. O corte de
            10 segundos fica numa faixa vazia dos dados, e qualquer limiar de 10 a 13 segundos
            produz os mesmos 277 blocos. Isso torna a divisão estável para visualização, mas não
            transforma os blocos observados em lotes internos comprovados.

            No gráfico principal, as faixas claras azuis e amarelas apenas alternam os blocos.
            As linhas originais continuam vermelha para Lula e azul para Bolsonaro. A tabela
            abaixo facilita a consulta dos horários e das quantidades de cada bloco.
            """
        ),
        code(
            '''
            display(tabela_distribuicao_intervalos)

            figura_intervalos, eixo_intervalos = plt.subplots(figsize=(12.5, 5.4))
            valores_intervalos = tabela_distribuicao_intervalos["Ocorrências"].to_numpy()
            barras_intervalos = eixo_intervalos.bar(
                tabela_distribuicao_intervalos["Intervalo"],
                valores_intervalos,
                color=["#4C78A8", "#4C78A8", "#4C78A8", "#E45756", "#F2CF5B", "#72B7B2"],
            )
            eixo_intervalos.set_yscale("symlog", linthresh=1)
            eixo_intervalos.set(
                title="Distribuição dos intervalos entre atualizações consecutivas",
                xlabel="Distância entre horários oficiais",
                ylabel="Ocorrências — escala logarítmica",
            )
            eixo_intervalos.grid(axis="y", color="#D9E2F2", linewidth=0.8)
            for barra, valor in zip(barras_intervalos, valores_intervalos, strict=True):
                rotulo = f"{int(valor):,}".replace(",", ".")
                eixo_intervalos.annotate(
                    rotulo,
                    (barra.get_x() + barra.get_width() / 2, float(valor)),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontweight="bold" if valor == 0 else "normal",
                )
            figura_intervalos.tight_layout()
            salvar_figura_svg(figura_intervalos, "distribuicao_intervalos.svg")

            tabela_blocos_exibicao = blocos_observados[[
                "BLOCO_OBSERVADO",
                "inicio_totalizacao",
                "fim_totalizacao",
                "quantidade_atualizacoes",
                "secoes_incorporadas",
                "votos_validos_incorporados",
                "bolsonaro_percentual_no_bloco",
                "variacao_bolsonaro_pp",
                "direcao_bolsonaro",
            ]].head(15).copy()
            tabela_blocos_exibicao.columns = [
                "bloco", "início", "fim", "atualizações", "seções", "votos válidos",
                "Bolsonaro no bloco (%)", "efeito no acumulado (p.p.)", "direção",
            ]
            tabela_blocos_exibicao["início"] = tabela_blocos_exibicao["início"].dt.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
            tabela_blocos_exibicao["fim"] = tabela_blocos_exibicao["fim"].dt.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
            display(tabela_blocos_exibicao)
            display(Markdown(
                f"**Resultado:** foram identificados **{quantidade_blocos} blocos observados**. "
                f"Entre os {len(intervalos_entre_blocos)} pares consecutivos, "
                f"**{blocos_entre_55_e_70} ({percentual_blocos_entre_55_e_70:.1f}%)** "
                f"começaram de 55 a 70 segundos depois do anterior; a mediana foi "
                f"**{mediana_intervalo_blocos:.0f} segundos**. A tabela acima mostra os "
                "15 primeiros; a tabela completa está em "
                "[`auditoria/blocos_totalizacao.csv`](../auditoria/blocos_totalizacao.csv)."
            ))
            '''
        ),
        markdown(
            """
            ## 1. Por que o percentual cai?

            Uma queda não significa retirada de votos: os votos acumulados nunca diminuem.
            O percentual de um candidato cai quando a participação dele no **novo incremento** é
            menor que a participação que possuía antes do incremento.

            A identidade usada abaixo é:

            `variação = peso do novo incremento × (percentual no incremento − percentual anterior)`

            Como existem apenas dois candidatos nos votos válidos, a variação percentual de
            Bolsonaro é o inverso da variação de Lula, salvo o arredondamento publicado.

            **Como ler o gráfico:** em cada horário, a barra cinza mostra o percentual de Lula
            antes do incremento e a vermelha mostra o percentual de Lula no incremento. Quando
            a vermelha fica abaixo da cinza, o percentual acumulado cai.
            """
        ),
        code(
            '''
            validos_acumulados = dados["QT_VOTOS_CONCORRENTES_ACUMULADO"].astype("int64")
            validos_antes = validos_acumulados - votos_validos_no_incremento
            lula_acumulado = dados["LULA_QT_VOTOS_TOT_ACUMULADO"].astype("int64")
            lula_no_incremento = dados["LULA_QT_VOTOS_TOT"].astype("int64")
            lula_antes = lula_acumulado - lula_no_incremento

            percentual_lula_antes = lula_antes.div(validos_antes).mul(100)
            percentual_lula_incremento = lula_no_incremento.div(votos_validos_no_incremento).mul(100)
            peso_incremento = votos_validos_no_incremento.div(validos_acumulados)
            variacao_lula_calculada = peso_incremento.mul(
                percentual_lula_incremento - percentual_lula_antes
            )
            variacao_lula_observada = participacao["LULA (13)"].diff()

            erro_formula = (
                variacao_lula_observada.iloc[1:] - variacao_lula_calculada.iloc[1:].to_numpy()
            ).abs()
            assert erro_formula.max() <= 0.000101, erro_formula.max()

            analise_incrementos = pd.DataFrame({
                "horário": indice,
                "variação_Lula_pp": variacao_lula_observada.to_numpy(),
                "Lula_antes_pct": percentual_lula_antes.to_numpy(),
                "Lula_no_incremento_pct": percentual_lula_incremento.to_numpy(),
                "votos_válidos_no_incremento": votos_validos_no_incremento.to_numpy(),
                "seções_no_incremento": secoes_no_incremento.to_numpy(),
            })
            maiores_quedas = analise_incrementos.nsmallest(10, "variação_Lula_pp").copy()
            maiores_quedas["rótulo"] = maiores_quedas.apply(
                lambda linha: (
                    f"{linha['horário']:%H:%M:%S}<br>"
                    f"{linha['variação_Lula_pp']:+.3f} p.p."
                ),
                axis=1,
            )

            tabela_quedas = maiores_quedas.copy()
            tabela_quedas["horário"] = tabela_quedas["horário"].dt.strftime("%d/%m/%Y %H:%M:%S")

            fig_composicao = go.Figure()
            for coluna, nome, cor in [
                ("Lula_antes_pct", "Percentual acumulado anterior", "#808080"),
                ("Lula_no_incremento_pct", "Percentual de Lula no incremento", "#D62728"),
            ]:
                fig_composicao.add_trace(go.Bar(
                    x=maiores_quedas["rótulo"],
                    y=maiores_quedas[coluna],
                    name=nome,
                    marker_color=cor,
                    text=maiores_quedas[coluna],
                    texttemplate="%{text:.1f}%",
                    textposition="outside",
                    customdata=np.column_stack([
                        maiores_quedas["variação_Lula_pp"],
                        maiores_quedas["votos_válidos_no_incremento"],
                        maiores_quedas["seções_no_incremento"],
                    ]),
                    hovertemplate=(
                        "%{x}<br>"
                        "%{fullData.name}: %{y:.4f}%<br>"
                        "Variação de Lula: %{customdata[0]:+.4f} p.p.<br>"
                        "Votos válidos no incremento: %{customdata[1]:,.0f}<br>"
                        "Seções no incremento: %{customdata[2]:,.0f}<extra></extra>"
                    ),
                ))
            fig_composicao.update_layout(
                title={
                    "text": "Nas maiores quedas, o incremento tinha percentual menor",
                    "x": 0.02,
                    "xanchor": "left",
                },
                template="plotly_white",
                height=600,
                barmode="group",
                dragmode="zoom",
                hovermode="closest",
                xaxis={"title": "Horário e tamanho da queda", "type": "category"},
                yaxis={
                    "title": "Percentual de Lula nos votos válidos",
                    "range": [0, 62],
                    "ticksuffix": "%",
                },
                showlegend=True,
                legend={
                    "orientation": "h",
                    "x": 0,
                    "xanchor": "left",
                    "y": 1.08,
                    "yanchor": "bottom",
                },
                margin={"l": 75, "r": 25, "t": 130, "b": 95},
            )
            fig_composicao.show(config=CONFIG_GRAFICO)
            display(Markdown(
                "**Conclusão:** nas maiores quedas, votos continuaram sendo acrescentados, "
                "mas o incremento tinha proporcionalmente menos votos para Lula que o "
                "acumulado anterior. Por isso a porcentagem caiu."
            ))
            '''
        ),
        markdown(
            """
            ## Relação temporal entre BUs recebidos e atualizações totalizadas

            Agora os BUs são agregados por `DT_BU_RECEBIDO`. A comparação não presume que
            receber e totalizar sejam o mesmo evento: ela procura a defasagem em que os fluxos
            ficam mais parecidos.

            Antes da correlação, há um controle mais básico: em cada atualização oficial,
            verificamos se o total de votos válidos já recebidos era suficiente para cobrir o
            total incorporado ao histórico até aquele instante.
            """
        ),
        code(
            '''
            caminho_boletins = str(FATOS_BOLETINS).replace("'", "''")
            chegadas_votos = con.execute(f"""
                SELECT
                    dt_bu_recebido,
                    sum(qt_votos) FILTER (WHERE nr_votavel = 13)::BIGINT AS lula,
                    sum(qt_votos) FILTER (WHERE nr_votavel = 22)::BIGINT AS bolsonaro,
                    sum(qt_votos) FILTER (WHERE nr_votavel IN (13, 22))::BIGINT AS validos
                FROM read_parquet('{caminho_fatos}', hive_partitioning=true)
                WHERE cd_cargo = 1
                GROUP BY dt_bu_recebido
                ORDER BY dt_bu_recebido
            """).df()
            chegadas_votos_sem_alerta_recebimento = con.execute(f"""
                WITH votos AS (
                    SELECT *
                    FROM read_parquet('{caminho_fatos}', hive_partitioning=true)
                    WHERE cd_cargo = 1
                ), boletins AS (
                    SELECT id_bu_cargo, dt_bu_recebido, dt_emissao_bu
                    FROM read_parquet('{caminho_boletins}', hive_partitioning=true)
                    WHERE cd_cargo = 1
                )
                SELECT
                    v.dt_bu_recebido,
                    sum(v.qt_votos) FILTER (WHERE v.nr_votavel = 13)::BIGINT AS lula,
                    sum(v.qt_votos) FILTER (WHERE v.nr_votavel = 22)::BIGINT AS bolsonaro,
                    sum(v.qt_votos) FILTER (WHERE v.nr_votavel IN (13, 22))::BIGINT AS validos
                FROM votos v
                JOIN boletins b USING (id_bu_cargo)
                WHERE NOT coalesce(b.dt_bu_recebido < b.dt_emissao_bu, false)
                GROUP BY v.dt_bu_recebido
                ORDER BY v.dt_bu_recebido
            """).df()
            quantidade_alertas_recebimento_presidente = int(con.execute(f"""
                SELECT count(*)
                FROM read_parquet('{caminho_boletins}', hive_partitioning=true)
                WHERE cd_cargo = 1 AND dt_bu_recebido < dt_emissao_bu
            """).fetchone()[0])
            assert quantidade_alertas_recebimento_presidente == 591
            chegadas_secoes = con.execute(f"""
                SELECT dt_bu_recebido, count(*)::BIGINT AS secoes
                FROM read_parquet('{caminho_boletins}', hive_partitioning=true)
                WHERE cd_cargo = 1
                GROUP BY dt_bu_recebido
                ORDER BY dt_bu_recebido
            """).df()
            resumo_bus = con.execute(f"""
                SELECT
                    count(*)::BIGINT,
                    sum(qt_aptos)::BIGINT,
                    sum(qt_comparecimento)::BIGINT
                FROM read_parquet('{caminho_boletins}', hive_partitioning=true)
                WHERE cd_cargo = 1
            """).fetchone()
            quantidade_bus, aptos_bus, comparecimento_bus = map(int, resumo_bus)

            secoes_historico = int(dados.iloc[-1]["QT_SECOES_TOT_ACUMULADO"])
            aptos_historico = int(dados.iloc[-1]["QT_APTOS_TOT_ACUMULADO"])
            comparecimento_historico = int(dados.iloc[-1]["QT_VOTOS_TOTAL_ACUMULADO"])
            diferenca_secoes_sem_linha = secoes_historico - quantidade_bus
            diferenca_aptos_sem_linha = aptos_historico - aptos_bus
            assert comparecimento_bus == comparecimento_historico
            assert diferenca_secoes_sem_linha == 47
            assert diferenca_aptos_sem_linha == 657

            chegadas = (
                chegadas_votos.merge(chegadas_secoes, on="dt_bu_recebido", how="outer")
                .fillna(0)
                .sort_values("dt_bu_recebido")
                .reset_index(drop=True)
            )
            chegadas["dt_bu_recebido"] = pd.to_datetime(chegadas["dt_bu_recebido"])
            medidas_fluxo = ["lula", "bolsonaro", "validos", "secoes"]
            chegadas[medidas_fluxo] = chegadas[medidas_fluxo].astype("int64")

            chegadas_acumuladas = chegadas.copy()
            chegadas_acumuladas[medidas_fluxo] = (
                chegadas_acumuladas[medidas_fluxo].cumsum()
            )
            recebidos_ate_atualizacao = pd.merge_asof(
                pd.DataFrame({"instante": indice}),
                chegadas_acumuladas.rename(columns={"dt_bu_recebido": "instante"}),
                on="instante",
                direction="backward",
            )
            recebidos_estritamente_antes = pd.merge_asof(
                pd.DataFrame({"instante": indice}),
                chegadas_acumuladas.rename(columns={"dt_bu_recebido": "instante"}),
                on="instante",
                direction="backward",
                allow_exact_matches=False,
            )

            oficial_acumulado = pd.DataFrame({
                "lula": dados["LULA_QT_VOTOS_TOT_ACUMULADO"].astype("int64"),
                "bolsonaro": dados["JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO"].astype("int64"),
                "validos": dados["QT_VOTOS_CONCORRENTES_ACUMULADO"].astype("int64"),
            })
            cobertura_ate_mesmo_segundo = recebidos_ate_atualizacao[
                ["lula", "bolsonaro", "validos"]
            ].sub(
                oficial_acumulado
            )
            cobertura_estritamente_antes = recebidos_estritamente_antes[
                ["lula", "bolsonaro", "validos"]
            ].sub(oficial_acumulado)
            assert cobertura_ate_mesmo_segundo.ge(0).all().all(), (
                cobertura_ate_mesmo_segundo.min()
            )
            assert cobertura_ate_mesmo_segundo.iloc[-1].eq(0).all(), (
                cobertura_ate_mesmo_segundo.iloc[-1]
            )
            excecoes_mesmo_segundo = pd.concat(
                [pd.DataFrame({"instante": indice}), cobertura_estritamente_antes],
                axis=1,
            ).loc[cobertura_estritamente_antes.lt(0).any(axis=1)]
            assert len(excecoes_mesmo_segundo) == 2

            display(pd.DataFrame([{
                "seções_no_histórico": secoes_historico,
                "BUs_representados_no_BWeb": quantidade_bus,
                "diferença_de_seções": diferenca_secoes_sem_linha,
                "diferença_de_aptos": diferenca_aptos_sem_linha,
                "diferença_de_comparecimento": comparecimento_historico - comparecimento_bus,
            }]))

            resumo_cobertura = pd.DataFrame({
                "medida": ["Votos de Lula", "Votos de Bolsonaro", "Votos válidos"],
                "menor_saldo_recebido_até_o_mesmo_segundo_menos_totalizado": [
                    int(cobertura_ate_mesmo_segundo["lula"].min()),
                    int(cobertura_ate_mesmo_segundo["bolsonaro"].min()),
                    int(cobertura_ate_mesmo_segundo["validos"].min()),
                ],
                "saldo_final": [
                    int(cobertura_ate_mesmo_segundo.iloc[-1]["lula"]),
                    int(cobertura_ate_mesmo_segundo.iloc[-1]["bolsonaro"]),
                    int(cobertura_ate_mesmo_segundo.iloc[-1]["validos"]),
                ],
            })
            display(resumo_cobertura)
            display(Markdown(
                "**Limite da resolução temporal:** quando se exigem BUs recebidos "
                "estritamente antes da atualização, aparecem duas exceções. Como ambas as "
                "fontes registram apenas o segundo inteiro, não é possível ordenar eventos "
                "que têm exatamente o mesmo horário."
            ))
            display(excecoes_mesmo_segundo)

            oficial_antes = pd.DataFrame({
                "lula": oficial_acumulado["lula"] - incrementos["LULA (13)"].to_numpy(),
                "bolsonaro": oficial_acumulado["bolsonaro"] - incrementos["JAIR BOLSONARO (22)"].to_numpy(),
                "validos": oficial_acumulado["validos"] - votos_validos_no_incremento.to_numpy(),
            })
            fila_disponivel_ate_o_instante = recebidos_ate_atualizacao[
                ["lula", "bolsonaro", "validos"]
            ].sub(oficial_antes)
            analise_incrementos["votos_válidos_recebidos_e_ainda_não_totalizados"] = (
                fila_disponivel_ate_o_instante["validos"].to_numpy()
            )
            analise_incrementos["Lula_pct_na_fila_disponível"] = (
                fila_disponivel_ate_o_instante["lula"]
                .div(fila_disponivel_ate_o_instante["validos"])
                .mul(100)
                .to_numpy()
            )
            colunas_fila = [
                "horário",
                "variação_Lula_pp",
                "votos_válidos_no_incremento",
                "Lula_no_incremento_pct",
                "votos_válidos_recebidos_e_ainda_não_totalizados",
                "Lula_pct_na_fila_disponível",
            ]
            display(analise_incrementos.nsmallest(10, "variação_Lula_pp")[colunas_fila])
            '''
        ),
        markdown(
            """
            ### 2. Quanto tempo depois do recebimento os votos aparecem na totalização?

            Para cada atraso de 0 a 180 segundos, comparamos o fluxo recebido no segundo `t`
            com o fluxo totalizado em `t + atraso`. O pico não significa que cada BU levou
            exatamente esse tempo; ele resume o comportamento predominante dos dois fluxos.

            **Como ler:** procure o ponto mais alto da linha. Ele indica o deslocamento de tempo
            que torna os dois fluxos mais parecidos. A correlação não é uma probabilidade: `0,395`
            não significa “39,5% de chance”.

            **O que significa “os dois fluxos são zero”:** depois de aplicar um atraso, comparamos
            dois segundos. No primeiro, nenhum voto válido aparece nos BUs com horário de
            recebimento naquele segundo; no segundo correspondente, não há votos válidos
            acrescentados pelo histórico oficial. Isso significa **ausência de movimento naquele
            par de segundos**, e não que os BUs tenham zero votos, que votos tenham desaparecido
            ou que o total acumulado tenha voltado a zero.
            """
        ),
        code(
            '''
            inicio_oficial = indice.min().floor("s")
            fim_oficial = indice.max().ceil("s")
            grade_segundos = pd.date_range(inicio_oficial, fim_oficial, freq="s")

            recebidos_segundo = (
                chegadas.set_index("dt_bu_recebido")[medidas_fluxo]
                .groupby(level=0).sum()
                .reindex(grade_segundos, fill_value=0)
            )
            recebidos_segundo_sem_alerta = (
                chegadas_votos_sem_alerta_recebimento.set_index("dt_bu_recebido")[[
                    "lula", "bolsonaro", "validos"
                ]]
                .groupby(level=0).sum()
                .reindex(grade_segundos, fill_value=0)
            )
            totalizados_segundo = pd.DataFrame({
                "lula": incrementos["LULA (13)"].to_numpy(),
                "bolsonaro": incrementos["JAIR BOLSONARO (22)"].to_numpy(),
                "validos": votos_validos_no_incremento.to_numpy(),
                "secoes": secoes_no_incremento.to_numpy(),
            }, index=indice).groupby(level=0).sum().reindex(grade_segundos, fill_value=0)

            def correlacao_com_atraso(origem, destino, atraso, somente_ativos=False):
                if atraso == 0:
                    x, y = origem, destino
                else:
                    x, y = origem[:-atraso], destino[atraso:]
                if somente_ativos:
                    ativos = (x != 0) | (y != 0)
                    x, y = x[ativos], y[ativos]
                return float(np.corrcoef(x, y)[0, 1])

            atrasos = np.arange(0, 181)
            nomes_medidas = {
                "secoes": "Quantidade de BUs/seções",
                "validos": "Votos válidos",
                "lula": "Votos de Lula",
                "bolsonaro": "Votos de Bolsonaro",
            }
            correlacoes_segundo = pd.DataFrame(index=atrasos)
            correlacoes_segundo_ativos = pd.DataFrame(index=atrasos)
            for medida in nomes_medidas:
                correlacoes_segundo[medida] = [
                    correlacao_com_atraso(
                        recebidos_segundo[medida].to_numpy(),
                        totalizados_segundo[medida].to_numpy(),
                        int(atraso),
                    )
                    for atraso in atrasos
                ]
                correlacoes_segundo_ativos[medida] = [
                    correlacao_com_atraso(
                        recebidos_segundo[medida].to_numpy(),
                        totalizados_segundo[medida].to_numpy(),
                        int(atraso),
                        somente_ativos=True,
                    )
                    for atraso in atrasos
                ]

            correlacao_validos_sem_alertas = pd.Series(
                [
                    correlacao_com_atraso(
                        recebidos_segundo_sem_alerta["validos"].to_numpy(),
                        totalizados_segundo["validos"].to_numpy(),
                        int(atraso),
                    )
                    for atraso in atrasos
                ],
                index=atrasos,
                name="sem_alertas_recebimento",
            )

            picos_correlacao = pd.DataFrame([
                {
                    "medida": nomes_medidas[medida],
                    "atraso_do_pico_em_segundos": int(correlacoes_segundo[medida].idxmax()),
                    "correlação_no_pico": float(correlacoes_segundo[medida].max()),
                    "atraso_do_pico_só_segundos_ativos": int(
                        correlacoes_segundo_ativos[medida].idxmax()
                    ),
                    "correlação_no_pico_só_segundos_ativos": float(
                        correlacoes_segundo_ativos[medida].max()
                    ),
                }
                for medida in nomes_medidas
            ])
            fig_atraso = go.Figure()
            pico_atraso_validos = int(correlacoes_segundo["validos"].idxmax())
            pico_correlacao_validos = float(correlacoes_segundo["validos"].max())
            pico_atraso_validos_ativos = int(
                correlacoes_segundo_ativos["validos"].idxmax()
            )
            pico_correlacao_validos_ativos = float(
                correlacoes_segundo_ativos["validos"].max()
            )
            pico_atraso_validos_sem_alertas = int(
                correlacao_validos_sem_alertas.idxmax()
            )
            pico_correlacao_validos_sem_alertas = float(
                correlacao_validos_sem_alertas.max()
            )
            recebidos_no_pico = recebidos_segundo["validos"].to_numpy()[
                :-pico_atraso_validos
            ]
            totalizados_no_pico = totalizados_segundo["validos"].to_numpy()[
                pico_atraso_validos:
            ]
            pares_ambos_zero = (
                (recebidos_no_pico == 0) & (totalizados_no_pico == 0)
            )
            quantidade_pares_pico = len(recebidos_no_pico)
            quantidade_pares_ambos_zero = int(pares_ambos_zero.sum())
            quantidade_pares_com_movimento = int((~pares_ambos_zero).sum())
            percentual_pares_ambos_zero = (
                quantidade_pares_ambos_zero / quantidade_pares_pico * 100
            )
            quantidade_pares_ambos_zero_texto = (
                f"{quantidade_pares_ambos_zero:,}".replace(",", ".")
            )
            quantidade_pares_pico_texto = f"{quantidade_pares_pico:,}".replace(",", ".")
            assert quantidade_pares_pico == 26173
            assert quantidade_pares_ambos_zero == 13979
            assert quantidade_pares_com_movimento == 12194
            fig_atraso.add_trace(go.Scatter(
                x=atrasos,
                y=correlacoes_segundo["validos"],
                name="Votos válidos",
                mode="lines",
                line={"width": 3, "color": "#2CA02C"},
                hovertemplate=(
                    "Atraso testado: %{x:.0f} segundos<br>"
                    "Semelhança dos fluxos: %{y:.4f}<extra></extra>"
                ),
            ))
            fig_atraso.add_trace(go.Scatter(
                x=atrasos,
                y=correlacoes_segundo_ativos["validos"],
                name="Somente segundos com movimento",
                mode="lines",
                line={"width": 2, "color": "#6F42C1", "dash": "dot"},
                hovertemplate=(
                    "Atraso testado: %{x:.0f} segundos<br>"
                    "Correlação sem pares ambos zerados: %{y:.4f}<extra></extra>"
                ),
            ))
            fig_atraso.add_trace(go.Scatter(
                x=[pico_atraso_validos],
                y=[pico_correlacao_validos],
                mode="markers+text",
                text=[f"Pico: {pico_atraso_validos} segundos"],
                textposition="top right",
                marker={"size": 12, "color": "#145A32"},
                hovertemplate=(
                    f"Maior semelhança<br>Atraso: {pico_atraso_validos} segundos<br>"
                    f"Correlação: {pico_correlacao_validos:.4f}<extra></extra>"
                ),
                showlegend=False,
            ))
            fig_atraso.add_vline(
                x=pico_atraso_validos,
                line_dash="dash",
                line_color="#333333",
            )
            fig_atraso.update_layout(
                title={
                    "text": "Maior semelhança: recebimento cerca de 1 minuto antes",
                    "x": 0.02,
                    "xanchor": "left",
                },
                template="plotly_white",
                height=540,
                dragmode="zoom",
                hovermode="x unified",
                xaxis={
                    "title": "Tempo entre o BU ser recebido e aparecer na totalização",
                    "range": [0, 180],
                    "ticksuffix": " s",
                },
                yaxis={"title": "Semelhança entre os fluxos (correlação)"},
                showlegend=True,
                legend={"orientation": "h", "y": 1.08, "yanchor": "bottom"},
                margin={"l": 85, "r": 45, "t": 85, "b": 75},
            )

            figura_correlacao, eixo_correlacao = plt.subplots(figsize=(12.5, 5.8))
            eixo_correlacao.plot(
                atrasos,
                correlacoes_segundo["validos"],
                color="#2CA02C",
                linewidth=2.2,
                label="Todos os segundos",
            )
            eixo_correlacao.plot(
                atrasos,
                correlacoes_segundo_ativos["validos"],
                color="#6F42C1",
                linewidth=1.8,
                linestyle="--",
                label="Somente segundos com movimento",
            )
            eixo_correlacao.axvline(
                pico_atraso_validos,
                color="#333333",
                linewidth=1.2,
                linestyle=":",
            )
            eixo_correlacao.scatter(
                [pico_atraso_validos, pico_atraso_validos_ativos],
                [pico_correlacao_validos, pico_correlacao_validos_ativos],
                color=["#145A32", "#6F42C1"],
                zorder=3,
            )
            eixo_correlacao.annotate(
                f"Pico: {pico_atraso_validos} s\\nr = {pico_correlacao_validos:.3f}",
                (pico_atraso_validos, pico_correlacao_validos),
                xytext=(12, -28),
                textcoords="offset points",
                ha="left",
                va="top",
                bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.85},
            )
            eixo_correlacao.set(
                title="Correlação entre recebimento e totalização por defasagem",
                xlabel="Defasagem aplicada ao fluxo recebido (segundos)",
                ylabel="Correlação de Pearson",
                xlim=(0, 180),
            )
            eixo_correlacao.grid(color="#D9E2F2", linewidth=0.8)
            eixo_correlacao.legend(loc="best", frameon=False)
            figura_correlacao.tight_layout()
            salvar_figura_svg(figura_correlacao, "correlacao_defasagem.svg")

            fig_atraso.show(config=CONFIG_GRAFICO)
            display(pd.DataFrame({
                "pares_no_atraso_de_61_segundos": [
                    "Ambos sem movimento",
                    "Pelo menos um fluxo com movimento",
                    "Total",
                ],
                "quantidade": [
                    quantidade_pares_ambos_zero,
                    quantidade_pares_com_movimento,
                    quantidade_pares_pico,
                ],
                "percentual": [
                    percentual_pares_ambos_zero,
                    100 - percentual_pares_ambos_zero,
                    100.0,
                ],
            }))
            display(pd.DataFrame({
                "cenário": [
                    "Todos os segundos",
                    "Somente segundos com movimento",
                    "Sem os 591 recebimentos anteriores à emissão",
                ],
                "atraso_do_pico_em_segundos": [
                    pico_atraso_validos,
                    pico_atraso_validos_ativos,
                    pico_atraso_validos_sem_alertas,
                ],
                "correlação_no_pico": [
                    pico_correlacao_validos,
                    pico_correlacao_validos_ativos,
                    pico_correlacao_validos_sem_alertas,
                ],
            }))
            display(Markdown(
                f"**Conclusão:** o fluxo de votos recebidos fica mais parecido com o fluxo "
                f"totalizado quando é deslocado **{pico_atraso_validos} segundos para a "
                f"frente** (correlação {pico_correlacao_validos:.3f}). Excluindo os pares em "
                f"que os dois fluxos estão sem movimento — **{quantidade_pares_ambos_zero_texto} "
                f"de {quantidade_pares_pico_texto} pares "
                f"({percentual_pares_ambos_zero:.1f}%)** —, "
                f"o pico fica em **{pico_atraso_validos_ativos} "
                f"segundos** (correlação {pico_correlacao_validos_ativos:.3f}). "
                f"Ao excluir os **{quantidade_alertas_recebimento_presidente}** BUs com "
                f"recebimento anterior à emissão, o pico permanece em "
                f"**{pico_atraso_validos_sem_alertas} segundos** (correlação "
                f"{pico_correlacao_validos_sem_alertas:.3f}). Isso é "
                "compatível com uma fila que incorpora BUs em atualizações; não quer "
                "dizer que todo BU individual levou exatamente esse tempo."
            ))
            '''
        ),
        markdown(
            """
            ### 3. Os BUs recebidos antecipam a direção das altas e quedas?

            O pico anterior fica próximo de um minuto. Para cada minuto, usamos o tamanho e a
            composição dos BUs recebidos para estimar se o percentual de Lula tenderia a subir
            ou cair. Depois comparamos essa estimativa com o que ocorreu no minuto seguinte.

            **Como ler:** cada ponto representa um minuto. Pontos no canto inferior esquerdo
            representam “queda estimada e queda observada”; pontos no canto superior direito,
            “alta estimada e alta observada”. Quanto mais os pontos seguem a diagonal, maior a
            concordância entre a chegada dos BUs e a variação posterior.
            """
        ),
        code(
            '''
            grade_minutos = pd.date_range(
                inicio_oficial.floor("min"), fim_oficial.floor("min"), freq="min"
            )
            recebidos_minuto = (
                chegadas.set_index("dt_bu_recebido")[medidas_fluxo]
                .resample("min").sum()
                .reindex(grade_minutos, fill_value=0)
            )
            totalizados_minuto = (
                pd.DataFrame({
                    "lula": incrementos["LULA (13)"].to_numpy(),
                    "bolsonaro": incrementos["JAIR BOLSONARO (22)"].to_numpy(),
                    "validos": votos_validos_no_incremento.to_numpy(),
                    "secoes": secoes_no_incremento.to_numpy(),
                }, index=indice)
                .resample("min").sum()
                .reindex(grade_minutos, fill_value=0)
            )

            comparacao_minuto = pd.DataFrame(index=grade_minutos)
            for medida in medidas_fluxo:
                comparacao_minuto[f"recebidos_{medida}"] = recebidos_minuto[medida]
                comparacao_minuto[f"totalizados_minuto_seguinte_{medida}"] = (
                    totalizados_minuto[medida].shift(-1)
                )
            comparacao_minuto["Lula_pct_recebidos"] = (
                comparacao_minuto["recebidos_lula"]
                .div(comparacao_minuto["recebidos_validos"])
                .mul(100)
            )
            comparacao_minuto["Lula_pct_totalizados_minuto_seguinte"] = (
                comparacao_minuto["totalizados_minuto_seguinte_lula"]
                .div(comparacao_minuto["totalizados_minuto_seguinte_validos"])
                .mul(100)
            )

            pares_volume = comparacao_minuto[[
                "recebidos_validos", "totalizados_minuto_seguinte_validos"
            ]].dropna()
            pares_volume_ativos = pares_volume.loc[pares_volume.ne(0).any(axis=1)]
            pares_composicao = comparacao_minuto[[
                "Lula_pct_recebidos", "Lula_pct_totalizados_minuto_seguinte"
            ]].dropna()
            correlacao_minuto_validos = float(pares_volume.corr().iloc[0, 1])
            correlacao_minuto_validos_ativos = float(
                pares_volume_ativos.corr().iloc[0, 1]
            )
            correlacao_minuto_composicao = float(pares_composicao.corr().iloc[0, 1])

            estado_minuto = (
                pd.DataFrame({
                    "Lula_pct": participacao["LULA (13)"].to_numpy(),
                    "validos_acumulados": validos_acumulados.to_numpy(),
                }, index=indice)
                .resample("min").last().ffill()
                .reindex(grade_minutos).ffill()
            )
            comparacao_minuto["variação_estimada_pelos_recebidos"] = (
                comparacao_minuto["recebidos_validos"]
                .div(
                    estado_minuto["validos_acumulados"]
                    + comparacao_minuto["recebidos_validos"]
                )
                .mul(
                    comparacao_minuto["Lula_pct_recebidos"]
                    - estado_minuto["Lula_pct"]
                )
            )
            comparacao_minuto["variação_observada_minuto_seguinte"] = (
                estado_minuto["Lula_pct"].diff().shift(-1)
            )
            pares_variacao = comparacao_minuto[[
                "variação_estimada_pelos_recebidos",
                "variação_observada_minuto_seguinte",
            ]].dropna()
            correlacao_minuto_variacao = float(pares_variacao.corr().iloc[0, 1])

            fig_variacao = go.Figure()
            fig_variacao.add_trace(go.Scatter(
                x=pares_variacao["variação_estimada_pelos_recebidos"],
                y=pares_variacao["variação_observada_minuto_seguinte"],
                text=pares_variacao.index.strftime("%d/%m/%Y %H:%M"),
                mode="markers",
                name="Cada ponto é um minuto",
                marker={
                    "size": 8,
                    "color": "#6F42C1",
                    "opacity": 0.65,
                    "line": {"width": 0.5, "color": "#3D2462"},
                },
                hovertemplate=(
                    "Minuto de recebimento: %{text}<br>"
                    "Variação estimada: %{x:+.4f} p.p.<br>"
                    "Variação observada depois: %{y:+.4f} p.p.<extra></extra>"
                ),
            ))
            limite_variacao = float(np.nanmax(np.abs(np.concatenate([
                pares_variacao["variação_estimada_pelos_recebidos"].to_numpy(),
                pares_variacao["variação_observada_minuto_seguinte"].to_numpy(),
            ])))) * 1.08
            reta_variacao_x = np.linspace(-limite_variacao, limite_variacao, 100)
            coef_variacao = np.polyfit(
                pares_variacao["variação_estimada_pelos_recebidos"],
                pares_variacao["variação_observada_minuto_seguinte"],
                1,
            )
            fig_variacao.add_trace(go.Scatter(
                x=reta_variacao_x,
                y=np.polyval(coef_variacao, reta_variacao_x),
                mode="lines",
                name="Tendência",
                line={"color": "#2F1747", "dash": "dash", "width": 2.5},
                hoverinfo="skip",
            ))
            fig_variacao.add_hline(y=0, line_color="#888888", line_width=1)
            fig_variacao.add_vline(x=0, line_color="#888888", line_width=1)
            fig_variacao.add_annotation(
                x=-limite_variacao * 0.7,
                y=-limite_variacao * 0.88,
                text="queda estimada<br>e queda observada",
                showarrow=False,
                font={"color": "#8B0000"},
            )
            fig_variacao.add_annotation(
                x=limite_variacao * 0.7,
                y=limite_variacao * 0.88,
                text="alta estimada<br>e alta observada",
                showarrow=False,
                font={"color": "#155724"},
            )
            fig_variacao.update_layout(
                title={
                    "text": (
                        "A chegada dos BUs antecipa a direção da variação posterior "
                        f"(correlação {correlacao_minuto_variacao:.3f})"
                    ),
                    "x": 0.02,
                    "xanchor": "left",
                },
                template="plotly_white",
                height=650,
                dragmode="zoom",
                hovermode="closest",
                xaxis={
                    "title": "Variação estimada pelos BUs recebidos (pontos percentuais)",
                    "range": [-limite_variacao, limite_variacao],
                    "zeroline": False,
                },
                yaxis={
                    "title": "Variação realmente observada no minuto seguinte",
                    "range": [-limite_variacao, limite_variacao],
                    "zeroline": False,
                    "scaleanchor": "x",
                    "scaleratio": 1,
                },
                showlegend=False,
                margin={"l": 90, "r": 40, "t": 90, "b": 85},
            )
            fig_variacao.show(config=CONFIG_GRAFICO)

            resumo_correlacoes = pd.DataFrame({
                "comparação": [
                    "Quantidade de votos recebidos × totalizados depois",
                    "Quantidade de votos (sem minutos ambos zerados)",
                    "Composição dos BUs recebidos × atualização posterior",
                    "Variação estimada × variação observada depois",
                ],
                "correlação": [
                    correlacao_minuto_validos,
                    correlacao_minuto_validos_ativos,
                    correlacao_minuto_composicao,
                    correlacao_minuto_variacao,
                ],
                "leitura_simples": [
                    "Os volumes acompanham quase juntos",
                    "Teste de sensibilidade sem silêncio comum",
                    "A composição das atualizações acompanha bem",
                    "A direção e a intensidade das variações acompanham bem",
                ],
            })
            display(resumo_correlacoes)
            display(Markdown(
                f"**Conclusão:** a correlação de **{correlacao_minuto_variacao:.3f}** mostra "
                "forte concordância entre o sinal calculado a partir dos BUs recebidos e a "
                "variação observada no minuto seguinte. Isso é compatível com os BUs recebidos "
                "alimentando a fila da totalização; não identifica cada BU de uma atualização."
            ))
            '''
        ),
        markdown("## Síntese da correlação"),
        code(
            '''
            recebidos_antes_inicio = chegadas[chegadas["dt_bu_recebido"] < inicio_oficial]
            pico_validos_segundos = int(correlacoes_segundo["validos"].idxmax())
            pico_validos_correlacao = float(correlacoes_segundo["validos"].max())
            maior_queda = analise_incrementos.nsmallest(1, "variação_Lula_pp").iloc[0]
            inteiro_br = lambda valor: f"{int(valor):,}".replace(",", ".")

            display(Markdown(f"""
            **Leitura simples dos resultados**

            - Foram comparadas **{inteiro_br(len(dados))} atualizações oficiais**,
              **{inteiro_br(quantidade_bus)} BUs representados no BWeb** de Presidente e
              **{inteiro_br(len(chegadas))} horários distintos de recebimento**.
            - O histórico contém **{inteiro_br(secoes_historico)} seções**, 47 a mais que o
              BWeb. A diferença soma 657 aptos e zero comparecimento, sendo compatível com
              seções sem linha de votável; por isso a cobertura acumulada é validada por votos,
              não pela contagem de seções.
            - Antes do início do histórico já constavam como recebidos
              **{inteiro_br(recebidos_antes_inicio['secoes'].sum())} BUs**, com
              **{inteiro_br(recebidos_antes_inicio['validos'].sum())} votos válidos**.
            - Em todas as {inteiro_br(len(dados))} atualizações, os acumulados recebidos de Lula,
              Bolsonaro e votos válidos eram maiores ou iguais aos acumulados já totalizados
              **quando recebimentos no mesmo segundo são incluídos**. Exigindo recebimento
              estritamente anterior, há duas exceções; a resolução de um segundo não permite
              ordenar os eventos empatados. No final, a diferença é zero.
            - No nível de segundos, o maior alinhamento dos votos válidos ocorre quando a chegada
              é deslocada **{pico_validos_segundos} segundos para a frente**, com correlação
              **{pico_validos_correlacao:.3f}**. Sem os pares em que ambos os fluxos são zero,
              o pico é de **{pico_atraso_validos_ativos} segundos**, com correlação
              **{pico_correlacao_validos_ativos:.3f}**.
            - Excluindo automaticamente os **{quantidade_alertas_recebimento_presidente} BUs**
              de Presidente com recebimento anterior à emissão, o pico permanece em
              **{pico_atraso_validos_sem_alertas} segundos**, com correlação
              **{pico_correlacao_validos_sem_alertas:.3f}**.
            - Por minuto, o volume recebido em `t` e o volume totalizado em `t + 1` têm correlação
              **{correlacao_minuto_validos:.3f}**; sem minutos em que ambos são zero, ela é
              **{correlacao_minuto_validos_ativos:.3f}**. A composição de Lula nessas atualizações tem correlação
              **{correlacao_minuto_composicao:.3f}**. O sinal de variação calculado com os BUs
              recebidos e a variação percentual observada depois têm correlação
              **{correlacao_minuto_variacao:.3f}**.
            - A maior queda individual de Lula ocorreu em
              **{maior_queda['horário']:%d/%m/%Y %H:%M:%S}**
              (**{maior_queda['variação_Lula_pp']:+.4f} p.p.**). O incremento tinha
              **{maior_queda['Lula_no_incremento_pct']:.3f}%** para Lula, abaixo do percentual acumulado
              anterior de **{maior_queda['Lula_antes_pct']:.3f}%**; por isso o percentual caiu.

            **Conclusão:** os dados são compatíveis com BUs recebidos entrando numa fila e sendo
            incorporados depois em atualizações. A correlação temporal sustenta essa relação operacional,
            mas não identifica quais BUs individuais compõem cada atualização e, sozinha, não
            prova causalidade nem avalia se o conteúdo de uma urna corresponde à intenção do eleitor.
            """))
            '''
        ),
        markdown("## Resumo eleitoral"),
        code(
            '''
            lider_por_atualizacao = acumulado.idxmax(axis=1)
            trocas_lideranca = int(lider_por_atualizacao.ne(lider_por_atualizacao.shift()).sum() - 1)
            lider_final = resultado.index[0]
            margem_final = int(resultado.iloc[0]["votos"] - resultado.iloc[1]["votos"])

            diferenca = acumulado["LULA (13)"] - acumulado["JAIR BOLSONARO (22)"]
            mudanca_sinal = diferenca.ge(0).ne(diferenca.shift().ge(0))
            mudanca_sinal.iloc[0] = False
            instante_lideranca_definitiva = diferenca.index[mudanca_sinal][-1]

            picos = pd.DataFrame({
                "horário_da_atualização": incrementos.idxmax(),
                "votos_adicionados": incrementos.max().astype("int64"),
            })

            print(f"Líder ao final: {lider_final}")
            print(f"Margem final: {margem_final:,} votos".replace(",", "."))
            print(f"Trocas de liderança entre atualizações: {trocas_lideranca}")
            print(
                "Início da liderança que permaneceu até o final: "
                f"{instante_lideranca_definitiva:%d/%m/%Y %H:%M:%S}"
            )
            print("\\nMaior entrada de votos por candidato em uma atualização:")
            display(picos)
            con.close()
            '''
        ),
        markdown(
            """
            ## Escopo e limitações

            - O histórico representa a evolução oficial da **totalização nacional**, não uma
              captura da tela de um navegador. Cache, rede ou frequência de atualização da tela
              podem ter feito um usuário enxergar vários pontos de uma só vez.
            - O arquivo não relaciona cada atualização aos identificadores individuais dos BUs;
              por isso, a conferência com os boletins é exata para os totais finais, não para a
              composição de cada atualização intermediária.
            - A correlação por minuto também reflete o perfil comum de volume ao longo da noite.
              Ela deve ser lida junto com o pico por segundo, a cobertura acumulada e a
              reconciliação final; correlação isolada não prova causalidade.
            - A fila calculada é agregada: ela comprova que havia votos recebidos suficientes,
              mas não identifica quais BUs foram escolhidos para cada atualização.
            - O histórico contém 47 seções a mais que os BUs representados no BWeb. Elas somam
              657 aptos e zero comparecimento; a correlação de quantidade de seções deve ser
              lida com essa diferença, enquanto a reconciliação dos votos fecha exatamente.
            - Os percentuais armazenados são frações arredondadas a seis casas; no gráfico são
              multiplicados por 100 e exibidos como porcentagem.
            - A fonte cobre apenas Presidente, Brasil, segundo turno de 2022.
            """
        ),
    ]

    for index, cell in enumerate(notebook.cells):
        cell.id = hashlib.sha256(
            f"{index}|{cell.cell_type}|{cell.source}".encode("utf-8")
        ).hexdigest()[:16]

    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    client.execute()
    for cell in notebook.cells:
        cell.metadata.pop("execution", None)
    temporary_notebook = NOTEBOOK_PATH.with_name(NOTEBOOK_PATH.name + ".part")
    nbf.write(notebook, temporary_notebook)
    temporary_notebook.replace(NOTEBOOK_PATH)
    print(f"Notebook gerado e executado: {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
