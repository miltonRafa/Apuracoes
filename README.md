# Apurações eleitorais

O repositório mantém código, documentação, auditoria e notebooks. Os arquivos brutos e as tabelas geradas ficam fora do Git e são reconstruídos pelo pipeline a partir do Portal de Dados Abertos do TSE.

## Reproduzir o segundo turno de 2022

```bash
cd 2t2022
./04_bi/executar_pipeline.sh
```

O comando executa a cadeia completa:

1. consulta a API do TSE e descobre os links de todas as UFs;
2. baixa ZIPs e arquivos SHA-512, com retomada;
3. valida a integridade e extrai os CSVs;
4. gera as tabelas Parquet para BI;
5. executa os controles de auditoria;
6. recria e executa o notebook de evolução dos votos.

Os ZIPs, CSVs, Parquets e o ambiente Python são ignorados pelo Git.
