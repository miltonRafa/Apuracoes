# Reconciliação adicional: detalhe da apuração por seção

Os ZIPs acrescentados em `01_origem_zip/` foram conferidos antes da análise: os 28 ZIPs
de BWeb conferem com seus SHA-512, e `detalhe_votacao_secao_2022.zip`,
`votacao_secao_2022_BR.zip` e o histórico passaram no CRC interno.

## Resultado novo

O arquivo `detalhe_votacao_secao_2022_BR.csv` permite ligar cada seção ao seu
`DT_PRIM_TOT_PARCIAL_HOR_TSE`. Para Presidente no segundo turno, a soma das seções cujo
primeiro horário de totalização já havia ocorrido reproduz **exatamente** as 5.286 linhas
do histórico nacional:

| Medida | Resultado |
| --- | ---: |
| Atualizações nacionais no histórico | 5.286 |
| Atualizações reproduzidas exatamente | 5.286 |
| Máxima diferença de seções | 0 |
| Máxima diferença de votos de Lula | 0 |
| Máxima diferença de votos de Bolsonaro | 0 |

Isso fortalece a análise anterior: o histórico nacional não apenas fecha nos totais
finais; em cada segundo publicado ele coincide com o conjunto de seções cuja primeira
totalização parcial já consta na fonte oficial. O resultado não revela ordem interna entre
seções que entram no mesmo segundo.

## Ligação com os BUs

O detalhe contém 472.075 seções. O BWeb tem 472.028, pois 47 seções têm zero
comparecimento e não possuem linha de votável. Nas 472.028 seções comuns,
`DT_RECEBIMENTO_BU_HOR_TSE` é idêntico a `DT_BU_RECEBIDO` em todos os casos.

| Defasagem BU recebido → primeira totalização | Segundos |
| --- | ---: |
| Mínima | 0 |
| Mediana | 36 |
| Percentil 95 | 69 |
| Percentil 99 | 90 |
| Máxima | 56.406 |

415.041 de 472.075 seções (87,92%) entraram em até 61 segundos; 470.751 (99,72%) em
até 120 segundos. As caudas longas são preservadas na fonte e não foram removidas.

## O que mudou

Não mudou a conclusão sobre o histórico oficial, os totais ou a impossibilidade de ordenar
eventos empatados dentro de um segundo. Mudou o grau de evidência: antes a relação entre
BUs recebidos e totalizações era inferida por correlação e cobertura acumulada; agora ela
é confirmada diretamente, seção a seção, para todas as atualizações nacionais.
