# Primeiro turno de 2026 — extração das fontes

Este pré-projeto prepara os arquivos oficiais de boletim de urna do primeiro turno. Ele
somente descobre, baixa, valida e extrai as fontes; não transforma os dados nem cria camada BI.

Quando a publicação oficial estiver completa:

```bash
./executar_preparacao.sh
```

O comando exige os 28 pares ZIP/SHA-512 (27 UFs e `ZZ`), aceita apenas URLs do CDN oficial
do TSE, retoma downloads interrompidos e valida o SHA-512 antes da extração. Cada ZIP deve
conter exatamente um CSV e um PDF. Os CSVs são gravados em `02_dados_csv/`, o leia-me comum
em `03_documentacao/` e as evidências em `auditoria/manifesto_downloads.json`.

Os ZIPs e CSVs são reproduzíveis e ficam fora do Git. O pré-projeto não foi executado nesta
revisão porque a publicação do primeiro turno de 2026 ainda pode mudar até sua versão final.
