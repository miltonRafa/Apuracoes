# Camada analítica das apurações

Esta pasta transforma os CSVs oficiais em um modelo próprio para BI, sem alterar `01_origem_zip/` nem `02_dados_csv/`.

## Executar e validar

Na pasta `2t2022`:

```bash
./04_bi/executar_pipeline.sh
```

Não é preciso cadastrar links individuais. O pipeline consulta a API oficial do TSE, encontra os 28 pares ZIP/SHA-512 do segundo turno, retoma downloads interrompidos, valida os hashes, extrai os CSVs e cria as pastas necessárias. Arquivos já íntegros são reutilizados.

Depois da preparação das fontes, o pipeline só publica `04_bi/dados/` quando a construção termina. Em seguida, o validador reconcilia a saída com os CSVs e encerra com erro se algum teste falhar. Por fim, o notebook é recriado e executado.

## Consultar

```bash
.venv/bin/python 04_bi/scripts/consultar_bi.py resumo
.venv/bin/python 04_bi/scripts/consultar_bi.py cargos
.venv/bin/python 04_bi/scripts/consultar_bi.py apuracao --cargo 1 --uf SP --limite 20
```

As evidências ficam em `auditoria/`: relatório legível, resultados em CSV/JSON, comparação por UF, alertas temporais, hashes SHA-256 das fontes e metadados da execução. Uma `FALHA` reprova a camada; um `ALERTA` preserva e destaca uma anomalia que já existe na fonte.

Consulte `GUIA_POWER_BI.md` para montar o modelo e as medidas.

## Notebook de análise

O notebook executado `notebooks/analise_evolucao_votos.ipynb` mostra a evolução dos votos acumulados, a participação nos votos válidos e o ritmo de entrada por candidato. Para recriá-lo isoladamente:

```bash
.venv/bin/python 04_bi/scripts/create_analysis_notebook.py
```
