# Relatório de validação da camada BI

**Status geral: APROVADO_COM_ALERTAS**

Executado em UTC: `2026-10-26T18:32:33.025095+00:00`

| Teste | Severidade | Status | Obtido | Esperado |
| --- | --- | --- | ---: | ---: |
| Quantidade de registros de votos | ERRO | OK | 2841231 | 2841231 |
| Total de votos | ERRO | OK | 190368252 | 190368252 |
| Quantidade de boletins por seção/cargo | ERRO | OK | 721068 | 721068 |
| Chaves duplicadas em fato_votos | ERRO | OK | 0 | 0 |
| Chaves duplicadas em fato_boletins | ERRO | OK | 0 | 0 |
| Consistência interna dos metadados do BU | ERRO | OK | 0 | 0 |
| Equação do eleitorado | ERRO | OK | 0 | 0 |
| Fechamento de votos por boletim | ERRO | OK | 0 | 0 |
| Horários de recebimento válidos | ERRO | OK | 0 | 0 |
| Impressão digital dos registros | ERRO | OK | 15038630024383966764 | 15038630024383966764 |
| Chaves duplicadas em fato_lotes_recebimento | ERRO | OK | 0 | 0 |
| Reconciliação de boletins nos lotes | ERRO | OK | 721068 | 721068 |
| Reconciliação de comparecimento nos lotes | ERRO | OK | 190368252.0 | 190368252 |
| Unicidade da dimensão localidade | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão localidade | ERRO | OK | 0 | 0 |
| Unicidade da dimensão cargo | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão cargo | ERRO | OK | 0 | 0 |
| Unicidade da dimensão votável | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão votável | ERRO | OK | 0 | 0 |
| Unicidade da dimensão tempo | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão tempo | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão UF | ERRO | OK | 0 | 0 |
| Partições publicadas em fato_votos | ERRO | OK | 28 | 28 |
| Partições publicadas em fato_boletins | ERRO | OK | 28 | 28 |
| Partições publicadas em fato_lotes_recebimento | ERRO | OK | 28 | 28 |
| Reconciliação por UF | ERRO | OK | 0 | 0 |
| Recebimento anterior à emissão | ALERTA | ALERTA | 600 | 0 |
| Emissão anterior ao encerramento | ALERTA | ALERTA | 1 | 0 |

Falhas impedem a aprovação. Alertas identificam anomalias já existentes na fonte e não alteram os valores publicados.

A ordem da apuração usa `DT_BU_RECEBIDO`. Boletins recebidos no mesmo segundo pertencem ao mesmo lote; o arquivo de origem não permite ordená-los entre si.
