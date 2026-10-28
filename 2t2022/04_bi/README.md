# Camada analítica das apurações

Esta pasta transforma os CSVs oficiais em um modelo próprio para BI, sem alterar `01_origem_zip/` nem `02_dados_csv/`.

A visão executiva, o diagrama da arquitetura e os resultados consolidados dos testes estão
no [README principal](../../README.md).

## O que esta análise responde

O projeto separa dois momentos:

- `DT_BU_RECEBIDO`: horário de recebimento informado na fonte do boletim;
- `DT_TOTALIZACAO`: quando uma atualização foi incorporada ao histórico nacional.

O resultado principal é simples: os votos dos BUs aparecem recebidos até o mesmo segundo
em que são necessários na totalização, e o fluxo recebido se parece mais com o fluxo
totalizado cerca de um minuto depois. As quedas percentuais acontecem quando a participação de um candidato
no incremento novo é menor que seu percentual acumulado anterior — não porque votos acumulados
tenham sido retirados.

A explicação completa, incluindo limites da análise, está em
`auditoria/SINTESE_CORRELACAO_BU_TOTALIZACAO.md`.

## Organização

```text
04_bi/
├── fontes/historico_totalizacao/   CSV oficial e leia-me preservados
├── dados/                           Parquets gerados pelo pipeline
├── auditoria/                       validações e síntese da correlação
├── graficos/                         SVGs vetoriais usados nos READMEs
├── notebooks/                       análise executada com gráficos interativos
└── scripts/                         preparação, construção, validação e notebook
```

## Executar e validar

Na pasta `2t2022`:

```bash
./04_bi/executar_pipeline.sh
```

Não é preciso cadastrar links individuais. O pipeline consulta a API oficial do TSE,
encontra os 28 pares ZIP/SHA-512 dos BUs e também o recurso do histórico da totalização,
retoma downloads interrompidos, valida os hashes, extrai os arquivos e cria as pastas
necessárias. Arquivos já íntegros são reutilizados.

O catálogo não fornece um hash para o ZIP do histórico. Por isso o projeto fixa o
SHA-256 do ZIP e dos dois arquivos internos, além de validar o CRC do ZIP. Se o conteúdo
remoto mudar, a preparação interrompe a execução em vez de misturar versões.

Depois da preparação das fontes, o pipeline só publica `04_bi/dados/` quando a construção
termina. Em seguida, o validador reconcilia a saída com os CSVs e encerra com erro se algum
teste falhar. Por fim, o notebook é recriado e executado e `auditoria/manifesto_saidas.csv`
registra o tamanho e o SHA-256 de todas as saídas.

Para conferir a integridade sem reconstruir:

```bash
.venv/bin/python 04_bi/scripts/finalize_audit.py --verificar
```

## Consultar

```bash
.venv/bin/python 04_bi/scripts/consultar_bi.py resumo
.venv/bin/python 04_bi/scripts/consultar_bi.py cargos
.venv/bin/python 04_bi/scripts/consultar_bi.py apuracao --cargo 1 --uf SP --limite 20
```

As evidências ficam em `auditoria/`: relatório legível, resultados em CSV/JSON, comparação por UF, alertas temporais, hashes SHA-256 das fontes e metadados da execução. Uma `FALHA` reprova a camada; um `ALERTA` preserva e destaca uma anomalia que já existe na fonte.

Consulte `GUIA_POWER_BI.md` para montar o modelo e as medidas.

## Notebook de análise

O notebook executado `notebooks/analise_evolucao_votos.ipynb` reproduz as 5.286
atualizações do histórico oficial, na ordem de `DT_TOTALIZACAO`. Os incrementos,
acumulados e percentuais vêm diretamente dessa fonte; os BUs são usados para conferir os
totais e analisar o fluxo de recebimento separadamente.

O notebook contém:

1. gráfico com todas as atualizações, percentual acumulado e variação por atualização;
2. faixas de fundo alternadas no próprio gráfico principal, delimitando os blocos
   observados, e tabela completa em `auditoria/blocos_totalizacao.csv`;
3. gráfico das maiores quedas comparando o percentual anterior com a composição do incremento;
4. correlação por defasagem de 0 a 180 segundos;
5. comparação por minuto entre BUs recebidos, atualizações totalizadas e quedas posteriores;
6. tabelas de reconciliação e da fila agregada disponível até o mesmo segundo das maiores quedas.

## Gráficos principais

Os gráficos abaixo são SVGs vetoriais gerados automaticamente pelo mesmo código do notebook,
e não capturas de tela. Clique em qualquer gráfico para abrir a análise interativa completa.

### Evolução percentual e blocos observados

[![Evolução percentual dos candidatos com os blocos observados](graficos/evolucao_percentual_blocos.svg)](notebooks/analise_evolucao_votos.ipynb)

### Distribuição dos intervalos entre atualizações

[![Distribuição dos intervalos entre atualizações consecutivas](graficos/distribuicao_intervalos.svg)](notebooks/analise_evolucao_votos.ipynb)

### Correlação por defasagem

[![Correlação entre recebimento e totalização por defasagem](graficos/correlacao_defasagem.svg)](notebooks/analise_evolucao_votos.ipynb)

Todos os gráficos aceitam zoom retangular, seleção pela legenda e detalhes ao passar o
mouse dentro do notebook. Para recriar o notebook e os SVGs:

```bash
.venv/bin/python 04_bi/scripts/create_analysis_notebook.py
```

## Números principais

- 5.286 atualizações oficiais;
- 277 blocos observados, delimitados por pausas de pelo menos 10 segundos;
- 91,7% dos inícios consecutivos separados por 55 a 70 segundos, com mediana de 65;
- 472.028 BUs de Presidente representados no BWeb;
- pico da correlação por segundo com defasagem de 61 segundos;
- correlação no pico de `0,395` contando toda a grade de segundos e `0,270` quando pares
  sem movimento em ambos os fluxos são excluídos; isso quer dizer que naquele segundo não
  houve votos válidos recebidos nem, após a defasagem, votos válidos acrescentados à
  totalização — não significa BU sem votos nem retirada de votos;
- correlação de `0,987` entre votos válidos recebidos por minuto e totalizados no minuto
  seguinte (`0,985` sem minutos em que ambos são zero);
- correlação de `0,812` entre a participação de Lula nesses dois fluxos;
- correlação de `0,886` entre a variação estimada pelos BUs recebidos e a variação
  percentual observada no minuto seguinte;
- totais finais de Lula, Bolsonaro, brancos e nulos reconciliados sem diferença.

Correlação descreve o alinhamento dos fluxos, mas não revela quais BUs individuais
compuseram cada atualização oficial e não prova causalidade isoladamente. Correlação não
é probabilidade e os valores altos por minuto refletem também o perfil comum de volume.

Na conferência acumulada, todos os votos necessários aparecem recebidos **até o mesmo
segundo** da atualização. Se a comparação exigir recebimento estritamente anterior, há
duas exceções; como as duas fontes têm resolução de um segundo, não é possível ordenar
eventos empatados dentro desse segundo.

O histórico contabiliza 472.075 seções, 47 a mais que o BWeb. A diferença corresponde a
657 aptos e zero comparecimento, compatível com seções sem linha de votável. Por isso a
cobertura acumulada é validada por votos; os totais de votos fecham exatamente.
