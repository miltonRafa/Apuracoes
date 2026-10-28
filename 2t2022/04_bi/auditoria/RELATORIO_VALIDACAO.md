# Relatório de validação da camada BI

**Status geral: APROVADO_COM_ALERTAS**

| Teste | Severidade | Status | Obtido | Esperado |
| --- | --- | --- | ---: | ---: |
| Quantidade de arquivos de origem | ERRO | OK | 28 | 28 |
| Abrangências da origem | ERRO | OK | 0 | 0 |
| UF coerente com o nome do arquivo | ERRO | OK | 0 | 0 |
| Escopo eleitoral da origem | ERRO | OK | 0 | 0 |
| Conversão dos campos numéricos obrigatórios | ERRO | OK | 0 | 0 |
| Conversão das datas obrigatórias | ERRO | OK | 0 | 0 |
| Conversão dos campos numéricos opcionais preenchidos | ERRO | OK | 0 | 0 |
| Conversão das datas opcionais preenchidas | ERRO | OK | 0 | 0 |
| Quantidade de registros de votos | ERRO | OK | 2841231 | 2841231 |
| Total de votos | ERRO | OK | 190368252 | 190368252 |
| Quantidade de boletins por seção/cargo | ERRO | OK | 721068 | 721068 |
| Chaves duplicadas em fato_votos | ERRO | OK | 0 | 0 |
| Chaves duplicadas em fato_boletins | ERRO | OK | 0 | 0 |
| Consistência interna de todos os metadados do BU | ERRO | OK | 0 | 0 |
| Campos obrigatórios em fato_boletins | ERRO | OK | 0 | 0 |
| Horário de emissão ausente | ALERTA | ALERTA | 1 | 0 |
| Campos obrigatórios em fato_votos | ERRO | OK | 0 | 0 |
| Equação do eleitorado | ERRO | OK | 0 | 0 |
| Fechamento de votos por boletim | ERRO | OK | 0 | 0 |
| Impressão digital dos registros | ERRO | OK | 15038630024383966764 | 15038630024383966764 |
| Chaves duplicadas em fato_recebimentos | ERRO | OK | 0 | 0 |
| Reconciliação de boletins recebidos | ERRO | OK | 721068 | 721068 |
| Reconciliação do comparecimento recebido | ERRO | OK | 190368252.0 | 190368252 |
| Consistência dos atributos das dimensões | ERRO | OK | 0 | 0 |
| Unicidade da dimensão localidade | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão localidade | ERRO | OK | 0 | 0 |
| Unicidade da dimensão cargo | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão cargo | ERRO | OK | 0 | 0 |
| Unicidade da dimensão votável | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão votável | ERRO | OK | 0 | 0 |
| Unicidade da dimensão tempo | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão tempo | ERRO | OK | 0 | 0 |
| Integridade referencial da dimensão UF | ERRO | OK | 0 | 0 |
| Partições lógicas em fato_votos | ERRO | OK | 28 | 28 |
| Partições lógicas em fato_boletins | ERRO | OK | 28 | 28 |
| Partições lógicas em fato_recebimentos | ERRO | OK | 28 | 28 |
| Reconciliação por UF | ERRO | OK | 0 | 0 |
| Recebimento anterior à emissão | ALERTA | ALERTA | 600 | 0 |
| Emissão anterior ao encerramento | ALERTA | ALERTA | 1 | 0 |

Falhas impedem a aprovação. Alertas registram anomalias presentes na fonte e não alteram os valores.

`DT_BU_RECEBIDO` é o horário de recebimento informado pela fonte. Registros no mesmo segundo podem ser agregados para análise, mas a fonte não demonstra um lote indivisível nem fornece ordem interna entre eles.
