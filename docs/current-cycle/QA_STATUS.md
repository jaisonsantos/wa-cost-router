# QA Status — Contatos/Opt-ins

## Automated Test Suites

| Suite | Comando | Resultado | Statements | Branches | Functions | Lines |
| --- | --- | --- | --- | --- | --- | --- |
| Backend | `make test-backend` | ✅ | 71% | — | — | 71% |
| Frontend | `npm test` | ✅ | 5.85% | 29.66% | 23.46% | 5.85% |

## Observações

- A suíte de backend inclui os diretórios `backend/app` e `backend/scripts`, publicando `backend/coverage.xml` para consumo posterior e expondo as lacunas relevantes (providers, rates e rules concentram a maior parte dos misses). 
- A suíte de frontend roda Vitest em modo `--run --coverage`, habilitando `@vitest/coverage-v8` e contabilizando os componentes de segmentos recém-criados; demais telas continuam sem testes associados e aparecem como não cobertas.
- Os resultados acima devem ser utilizados como linha de base para as execuções de QA do ciclo corrente, especialmente para monitorar a evolução das pastas de contatos e segmentação.
