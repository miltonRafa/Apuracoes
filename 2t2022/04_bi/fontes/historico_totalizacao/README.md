# Histórico oficial da totalização presidencial

Esta pasta recebe, sem transformação, a fonte complementar usada para reproduzir a ordem
oficial das atualizações do segundo turno de 2022. O conteúdo é baixado automaticamente
por `../../scripts/prepare_sources.py` a partir do
[recurso oficial do Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2022/resource/7cd53725-5dc5-4954-aee9-7dbf4097d26c).

## Arquivos

- `Historico_Totalizacao_Presidente_BR_2T_2022.csv`: 5.286 atualizações nacionais na
  ordem de `DT_TOTALIZACAO`.
- `leiame.pdf`: documentação que acompanhou o CSV.

## Papel de cada fonte

- O histórico informa **quando cada atualização entrou na totalização** e quantos votos foram
  acrescentados naquele momento.
- Os arquivos `bweb_2t_*` informam **quando cada BU foi recebido** e os resultados por
  seção.
- O notebook compara os dois relógios, mas não presume que `DT_BU_RECEBIDO` e
  `DT_TOTALIZACAO` sejam o mesmo evento.

## Integridade local

O recurso oficial não oferece um arquivo de hash separado. O pipeline valida o CRC do ZIP
e fixa os seguintes SHA-256 para impedir troca silenciosa de versão:

```text
1f12128fbcfacab755e0e83d9c0a350ed99ae68ea3d024aaa7bc58fe0c1dda3c  Historico_Totalizacao_Presidente_BR_2T_2022.zip
00013c958f13b2cf1a842c4398ca7cb52cf5ef46d26ce91f99c1a0ad8d0f663d  Historico_Totalizacao_Presidente_BR_2T_2022.csv
453cf754ad71b7bd9bcd31303fd14aefdecb7d091388ba585706ebd3c03d763f  leiame.pdf
```

Esses hashes registram a cópia usada no projeto; não são hashes publicados pelo TSE.
O CSV, o PDF e o ZIP são reproduzíveis e ficam fora do Git; este README e os hashes
esperados permanecem versionados.
