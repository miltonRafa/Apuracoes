# Síntese: chegada dos BUs e quedas na totalização

## Resposta curta

As quedas percentuais observadas no gráfico são explicadas pela composição dos incrementos
publicados no histórico. Os BUs aparecem como recebidos até o mesmo segundo em que seus
votos são incorporados, e os fluxos ficam mais semelhantes quando o
recebimento é comparado com a totalização aproximadamente um minuto depois.

Isso é compatível com uma relação operacional de fila e publicação em atualizações. Não é
prova de que cada BU recebido em determinado minuto pertence à atualização publicada no
minuto seguinte, porque o histórico agregado não publica a lista de BUs de cada atualização.

## O que foi comparado

- 5.286 linhas do histórico oficial, ordenadas por `DT_TOTALIZACAO`;
- 472.028 BUs de Presidente representados no BWeb;
- 11.388 instantes distintos de `DT_BU_RECEBIDO`;
- votos de Lula, Bolsonaro e o total de votos válidos em cada fluxo.

`DT_BU_RECEBIDO` é o horário de recebimento informado no BWeb. `DT_TOTALIZACAO` é o horário
de uma atualização do histórico nacional. Comparar os dois como se fossem o mesmo
relógio produziria uma interpretação incorreta.

## Principais resultados

1. Em todas as 5.286 atualizações, o acumulado de votos válidos recebido **até o mesmo
   segundo** era maior ou igual ao acumulado totalizado. Exigindo recebimento estritamente
   anterior, há duas exceções (`20:23:44` e `20:29:07`); a resolução de um segundo não
   permite ordenar esses empates. O saldo final é zero.
2. No nível de segundos, a correlação do volume de votos válidos atinge o maior valor
   com recebimentos antecedendo a totalização em 61 segundos: `r = 0,395`. Excluindo pares
   em que os dois fluxos são zero, o pico permanece em 61 segundos e cai para `r = 0,270`.
3. Agregando por minuto, o volume recebido em `t` e o totalizado em `t + 1` apresentam
   `r = 0,987` (`r = 0,985` sem minutos em que ambos são zero). A participação de Lula
   nos dois fluxos apresenta `r = 0,812`.
4. Usando o tamanho e a composição dos BUs recebidos em `t` para estimar a direção da
   mudança, a correlação com a variação percentual observada em `t + 1` é `r = 0,886`.
5. A soma final do histórico coincide exatamente com a soma dos BUs para Lula,
   Bolsonaro, votos brancos e nulos.

## Blocos observados no histórico

O histórico não fornece um identificador interno de lote nem a lista de BUs de cada
atualização. Ainda assim, os horários permitem delimitar **rajadas observáveis** de
totalização. Dentro dessas rajadas, os intervalos consecutivos ficam entre 1 e 9 segundos;
não há intervalos de 10, 11 ou 12 segundos; o próximo valor observado é 13 segundos. Por
isso, esta análise considera que uma pausa de pelo menos 10 segundos inicia um novo bloco.

Esse critério encontra 277 blocos. Dos 276 intervalos entre seus inícios, 253 (91,7%) ficam
entre 55 e 70 segundos, e a mediana é 65 segundos. Isso confirma que o padrão visual próximo
de um minuto existe no histórico oficial. Ele descreve ciclos de publicação/processamento,
mas não permite afirmar que cada bloco seja um lote interno indivisível nem identificar os
BUs individuais que o compõem.

A tabela completa com início, fim, duração, quantidade de atualizações, seções, votos,
composição e efeito percentual está em `blocos_totalizacao.csv`. O notebook marca a mesma
sequência com faixas de fundo alternadas no próprio gráfico oficial das atualizações.

O histórico contabiliza 472.075 seções, 47 a mais que as seções representadas no BWeb.
A diferença soma 657 aptos e zero comparecimento. Isso é compatível com seções sem uma
linha de votável no BWeb; por esse motivo, a cobertura da fila é validada pelos votos,
enquanto a correlação de quantidade de seções é apresentada com essa ressalva.

A correlação por minuto é alta em parte porque os dois fluxos compartilham o mesmo perfil
de volume ao longo da noite. O pico por segundo, a cobertura acumulada e a reconciliação
final são verificações complementares; nenhum número isolado deve ser interpretado como
prova causal. Correlação também não é probabilidade: `r = 0,395` não significa 39,5% de
chance de uma hipótese ser verdadeira. Esta análise não calcula uma probabilidade de fraude.

O notebook recalcula automaticamente o teste de sensibilidade: há 591 BUs de Presidente
cujo horário informado de recebimento antecede o de emissão e um
caso em que a emissão antecede o encerramento. Esses registros permanecem em
`alertas_temporais.csv`; não foram corrigidos artificialmente. Excluí-los praticamente não
altera o pico dos votos válidos (`61` segundos, `r = 0,395`), o que funciona como teste de
sensibilidade, mas não resolve a causa dos horários anômalos.

A estimativa de variação usa os BUs recebidos no minuto como aproximação da próxima atualização.
Ela serve para medir sinal e intensidade aproximada, não para afirmar que a composição
individual daquela atualização foi identificada.

## Por que a linha percentual cai

Para um candidato, a variação obedece à identidade:

```text
variação percentual
  = peso do novo incremento × (percentual do candidato no incremento − percentual anterior)
```

Se Lula tinha 53% antes de uma atualização e o novo incremento tem 40%, todos os votos
continuam sendo somados, mas seu percentual acumulado diminui. Como só existem dois
candidatos entre os votos válidos do segundo turno, a variação percentual de Bolsonaro é
o inverso da de Lula, salvo o arredondamento publicado.

A maior queda individual de Lula ocorreu em `30/10/2022 17:06:55`:

- variação: `−2,2584` ponto percentual;
- votos válidos no incremento: `40.930`;
- participação de Lula no incremento: `39,5358%`;
- participação de Lula antes do incremento: aproximadamente `53,9001%`.

Antes dessa atualização, os dados públicos já indicavam votos recebidos e ainda não
totalizados suficientes para cobrir o incremento até aquele mesmo segundo. Isso mostra
disponibilidade agregada na fila,
mas não permite nomear os BUs que formaram aquela atualização.

## O que a análise permite concluir

- As quedas são explicadas aritmeticamente pelo tamanho e pela composição dos incrementos.
- A chegada dos BUs antecede e acompanha fortemente o fluxo posterior de totalização.
- Os dados são compatíveis com recebimento, fila e publicação em atualizações.

## O que a análise não permite concluir

- Não identifica a composição exata de cada atualização oficial por seção.
- Correlação temporal não comprova causalidade por si só.
- Não verifica se o conteúdo registrado dentro de uma urna corresponde à intenção de
  cada eleitor; isso exige outros artefatos de auditoria.
- Não demonstra fraude nem sua ausência em uma urna específica.

Os cálculos, as tabelas e os gráficos interativos estão no notebook
`../notebooks/analise_evolucao_votos.ipynb` e são recriados por
`../scripts/create_analysis_notebook.py`.
