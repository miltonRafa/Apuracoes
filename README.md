# Apurações eleitorais

O repositório mantém código, documentação, auditoria, gráficos vetoriais e notebooks. Os arquivos brutos e as tabelas geradas ficam fora do Git e são reconstruídos pelo pipeline a partir do Portal de Dados Abertos do TSE.

## Reproduzir o segundo turno de 2022

```bash
cd 2t2022
./04_bi/executar_pipeline.sh
```

O comando executa a cadeia completa:

1. consulta a API do TSE e descobre os links de todas as UFs e do histórico da totalização;
2. baixa os ZIPs e arquivos SHA-512, com retomada;
3. valida SHA-512 dos BUs e CRC/SHA-256 do histórico, depois extrai os arquivos;
4. gera as tabelas Parquet para BI;
5. executa os controles de auditoria;
6. recria e executa o notebook de evolução dos votos e exporta os gráficos SVG;
7. gera e verifica um manifesto SHA-256 de todas as saídas publicadas.

Os ZIPs, CSVs brutos, fontes reproduzíveis, Parquets e o ambiente Python são ignorados
pelo Git. O código, os hashes esperados e a documentação permanecem versionados.

## Gráficos principais do segundo turno de 2022

Estes gráficos são SVGs vetoriais gerados pelo pipeline a partir das fontes analisadas,
não capturas de tela. Clique em qualquer um para abrir o notebook interativo com zoom e hover.

### Evolução percentual e blocos observados

[![Evolução percentual dos candidatos com os blocos observados](2t2022/04_bi/graficos/evolucao_percentual_blocos.svg)](2t2022/04_bi/notebooks/analise_evolucao_votos.ipynb)

### Distribuição dos intervalos entre atualizações

[![Distribuição dos intervalos entre atualizações consecutivas](2t2022/04_bi/graficos/distribuicao_intervalos.svg)](2t2022/04_bi/notebooks/analise_evolucao_votos.ipynb)

### Correlação por defasagem

[![Correlação entre recebimento e totalização por defasagem](2t2022/04_bi/graficos/correlacao_defasagem.svg)](2t2022/04_bi/notebooks/analise_evolucao_votos.ipynb)

Pré-requisitos: Python 3.12 ou compatível, suporte a `venv`, internet e espaço em disco
para os arquivos brutos e Parquets. O ambiente e as dependências Python são criados pelo
próprio comando.

## Preparação do primeiro turno de 2026

`1t2026/` contém um pré-projeto que baixa, valida e extrai os CSVs oficiais, sem criar
camada BI. Ele deve ser executado apenas quando a publicação final estiver disponível:

```bash
cd 1t2026
./executar_preparacao.sh
```

## Preparação do segundo turno de 2026

O diretório `2t2026/` contém um pré-projeto separado que somente descobre, baixa e valida
os ZIPs oficiais. Ele não contém transformação ou camada BI.

Quando a publicação oficial estiver disponível:

```bash
cd 2t2026
./executar_download.sh
```
