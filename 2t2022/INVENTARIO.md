# Inventário de apurações

- Fonte: arquivos `bweb_2t_*_311020221535.zip` recebidos nesta pasta.
- Arquivos CSV extraídos: 28.
- Organização:
  - `01_origem_zip/`: pacotes originais preservados.
  - `02_dados_csv/`: dados de apuração por UF.
  - `03_documentacao/`: leia-me fornecido na fonte (idêntico nos pacotes).

| UF | CSV | Tamanho (bytes) | ZIP de origem |
| --- | --- | ---: | --- |
| AC | `bweb_2t_AC_311020221535.csv` | 3695151 | `bweb_2t_AC_311020221535.zip` |
| AL | `bweb_2t_AL_311020221535.csv` | 24810986 | `bweb_2t_AL_311020221535.zip` |
| AM | `bweb_2t_AM_311020221535.csv` | 27043274 | `bweb_2t_AM_311020221535.zip` |
| AP | `bweb_2t_AP_311020221535.csv` | 3038466 | `bweb_2t_AP_311020221535.zip` |
| BA | `bweb_2t_BA_311020221535.csv` | 126621192 | `bweb_2t_BA_311020221535.zip` |
| CE | `bweb_2t_CE_311020221535.csv` | 41302440 | `bweb_2t_CE_311020221535.zip` |
| DF | `bweb_2t_DF_311020221535.csv` | 12452298 | `bweb_2t_DF_311020221535.zip` |
| ES | `bweb_2t_ES_311020221535.csv` | 34440142 | `bweb_2t_ES_311020221535.zip` |
| GO | `bweb_2t_GO_311020221535.csv` | 26730496 | `bweb_2t_GO_311020221535.zip` |
| MA | `bweb_2t_MA_311020221535.csv` | 28778601 | `bweb_2t_MA_311020221535.zip` |
| MG | `bweb_2t_MG_311020221535.csv` | 92121296 | `bweb_2t_MG_311020221535.zip` |
| MS | `bweb_2t_MS_311020221535.csv` | 25854055 | `bweb_2t_MS_311020221535.zip` |
| MT | `bweb_2t_MT_311020221535.csv` | 13587226 | `bweb_2t_MT_311020221535.zip` |
| PA | `bweb_2t_PA_311020221535.csv` | 31993576 | `bweb_2t_PA_311020221535.zip` |
| PB | `bweb_2t_PB_311020221535.csv` | 36133859 | `bweb_2t_PB_311020221535.zip` |
| PE | `bweb_2t_PE_311020221535.csv` | 77303232 | `bweb_2t_PE_311020221535.zip` |
| PI | `bweb_2t_PI_311020221535.csv` | 15937530 | `bweb_2t_PI_311020221535.zip` |
| PR | `bweb_2t_PR_311020221535.csv` | 47220847 | `bweb_2t_PR_311020221535.zip` |
| RJ | `bweb_2t_RJ_311020221535.csv` | 63453453 | `bweb_2t_RJ_311020221535.zip` |
| RN | `bweb_2t_RN_311020221535.csv` | 13940262 | `bweb_2t_RN_311020221535.zip` |
| RO | `bweb_2t_RO_311020221535.csv` | 15377941 | `bweb_2t_RO_311020221535.zip` |
| RR | `bweb_2t_RR_311020221535.csv` | 2131143 | `bweb_2t_RR_311020221535.zip` |
| RS | `bweb_2t_RS_311020221535.csv` | 102177207 | `bweb_2t_RS_311020221535.zip` |
| SC | `bweb_2t_SC_311020221535.csv` | 60293255 | `bweb_2t_SC_311020221535.zip` |
| SE | `bweb_2t_SE_311020221535.csv` | 20579517 | `bweb_2t_SE_311020221535.zip` |
| SP | `bweb_2t_SP_311020221535.csv` | 380518063 | `bweb_2t_SP_311020221535.zip` |
| TO | `bweb_2t_TO_311020221535.csv` | 6990822 | `bweb_2t_TO_311020221535.zip` |
| ZZ | `bweb_2t_ZZ_311020221535.csv` | 1837151 | `bweb_2t_ZZ_311020221535.zip` |

PDFs de leia-me únicos por SHA-256: 1.

## Camada preparada para BI

- `04_bi/dados/`: fatos e dimensões em Parquet, com dimensões também disponíveis em CSV UTF-8.
- `04_bi/auditoria/`: reconciliações, hashes das fontes, relatório de validação e alertas de qualidade.
- `04_bi/auditoria/manifesto_saidas.csv`: tamanho e SHA-256 das saídas publicadas pelo pipeline.
- `04_bi/GUIA_POWER_BI.md`: relacionamentos e medidas DAX sugeridas.
- `04_bi/executar_pipeline.sh`: reconstrói e revalida toda a camada sem alterar os dados originais.
- `04_bi/scripts/prepare_sources.py`: descobre os links na API do TSE, baixa, valida SHA-512 e extrai as fontes.
- `04_bi/notebooks/analise_evolucao_votos.ipynb`: gráficos executados das 5.286 atualizações oficiais, com zoom retangular, variação por atualização e faixas de fundo para 277 blocos observados no gráfico principal.
- `04_bi/graficos/`: três SVGs vetoriais gerados pelo notebook e incorporados aos READMEs.
- `04_bi/auditoria/blocos_totalizacao.csv`: tabela dos blocos observados com início, fim, duração, seções, votos, composição e efeito percentual.

## Histórico oficial da totalização

`04_bi/fontes/historico_totalizacao/` recebe o CSV agregado e seu leia-me. O script
`04_bi/scripts/prepare_sources.py` descobre o ZIP pelo identificador do recurso oficial,
baixa, valida CRC e SHA-256 e extrai os dois arquivos. O notebook usa `DT_TOTALIZACAO` e
os campos de incremento/acumulado para reproduzir a evolução oficial. Os CSVs de BU
permanecem separados e são usados para conferir os totais e medir a relação entre
`DT_BU_RECEBIDO` e `DT_TOTALIZACAO`.

A interpretação resumida está em
`04_bi/auditoria/SINTESE_CORRELACAO_BU_TOTALIZACAO.md`.
