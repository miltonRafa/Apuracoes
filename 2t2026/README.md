# Segundo turno de 2026 — preparação das fontes

Este é um pré-projeto somente para baixar os arquivos oficiais de boletim de urna. Ele não extrai CSVs, não transforma dados e não cria camada BI.

## Estado atual

O pipeline foi preparado, mas ainda não foi executado. O endereço esperado da API está em `config.json` e deve ser conferido quando a publicação oficial de 2026 estiver disponível.

## Executar futuramente

Na pasta `2t2026`:

```bash
./executar_download.sh
```

O comando usa apenas a biblioteca padrão do Python e:

1. consulta o catálogo do TSE;
2. localiza os pares ZIP/SHA-512 do segundo turno;
3. exige as 27 UFs e `ZZ` (exterior);
4. baixa com retomada após interrupções;
5. só publica cada ZIP depois de validar o SHA-512 oficial;
6. grava `auditoria/manifesto_downloads.json`.

Os arquivos serão colocados em `01_origem_zip/`, pasta ignorada pelo Git. Uma nova execução reaproveita os ZIPs que continuarem íntegros.

Se o TSE estiver publicando os arquivos gradualmente, é possível antecipar somente os pares completos já disponíveis:

```bash
./executar_download.sh --permitir-parcial
```

Sem essa opção, uma publicação incompleta encerra antes de qualquer download. Se o TSE alterar o identificador do conjunto de dados ou o formato da publicação, ajuste `api_url` em `config.json` antes de executar.

O script valida que `ufs_esperadas` contém exatamente as 28 abrangências; reduzir essa
lista no arquivo de configuração não permite declarar como completa uma publicação parcial.
