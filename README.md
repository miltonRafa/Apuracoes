# Apurações eleitorais

O repositório mantém código, documentação, auditoria e notebooks. Os arquivos brutos e as tabelas geradas ficam fora do Git e são reconstruídos pelo pipeline a partir do Portal de Dados Abertos do TSE.

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
6. recria e executa o notebook de evolução dos votos;
7. gera e verifica um manifesto SHA-256 de todas as saídas publicadas.

Os ZIPs, CSVs brutos, fontes reproduzíveis, Parquets e o ambiente Python são ignorados
pelo Git. O código, os hashes esperados e a documentação permanecem versionados.

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
