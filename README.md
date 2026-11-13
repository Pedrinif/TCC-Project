# ECOMUP Project

**Estudo computacional de otimização em metodologias utilizadas em processos industriais**
Trabalho de Graduação — Engenharia de Computação, Universidade de Taubaté (2026)
Miguel de Paulo Leite de Oliveira e Pedro Lauria Nassif · Orientador: Prof. Me. Julio Cesar Gonçalves

Processos industriais e logísticos são modelados como **grafos direcionados** e analisados de duas formas:
**análise estrutural** (capacidade por grupo de trabalhadores, caminho crítico e corte mínimo, sem simular) e
**simulação de eventos discretos** com réplicas e intervalo de confiança de 95%. O sistema aponta o gargalo
e estima quantos trabalhadores alocar em cada grupo.

---

## Como abrir o programa

```bash
cd TCC-Project && .venv/bin/streamlit run app.py
```

Depois abra `http://localhost:8501` no navegador. Para fechar, `Ctrl + C` no terminal.

Na primeira vez (ou em outro computador), instale as dependências:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

O botão no topo da barra lateral alterna entre modo claro e escuro.

## As duas páginas

| Página | Modelos | O que faz |
|---|---|---|
| **app** (principal) | M1, M2, M3 | Armazém de paletes: rede, filas, utilização, comparativo de topologias e análise de sensibilidade da capacidade |
| **Processos reais** (menu lateral) | M4, M5 | Grafo interativo com atividades e trabalhadores, resultados com IC 95%, análise estrutural, varredura do nº de trabalhadores, fonte e premissas, exportação para Excel |

## Os seis modelos (Tabela 4 do texto)

| Modelo | Origem | Onde está |
|---|---|---|
| M1 Simples, M2 Múltiplas Docas, M3 Pipeline | Protótipo | `src/rede.py` |
| M4 Recebimento de paletes | Saderova et al. (2022) | `processos/recebimento_saderova.yaml` |
| M5 Turnaround de Boeing 737-800 | San Antonio et al. (2017) | `processos/turnaround_b737.yaml` |
| M6 Linha de montagem | Instâncias SALBP | `processos/salbp/` + `src/salbp.py` |

Para modelar um processo novo, copie um YAML de `processos/`, troque trabalhadores, atividades
(`predecessoras`) e distribuições (`constante`, `uniforme`, `triangular`, `normal`, `exponencial`,
`weibull`, `lognormal`, `soma`) e preencha `fonte` e `premissas`.

## Reproduzir os resultados do texto

Cada comando imprime uma tabela e grava um CSV em `resultados/`. Padrão: 30 réplicas, semente base 1000.

| Experimento | Tabela / seção do texto | Comando |
|---|---|---|
| Testes automatizados (28) | Seção 4.1.1 | `.venv/bin/python -m pytest` |
| Verificação das filas M/M/1 e M/M/2 | Tabela 6 | `.venv/bin/python validar.py filas` |
| Validação M4 | Tabela 7 | `.venv/bin/python validar.py recebimento` |
| E6, validação M5 (30 réplicas) | Tabela 8 | `.venv/bin/python validar.py turnaround --replicas 30` |
| M5 com 200 réplicas | Seções 4.1.1 e 4.1.4 | `.venv/bin/python validar.py turnaround --replicas 200` |
| E1, E2, modelos base | Tabelas 12 e 13 | `.venv/bin/python validar.py basico --replicas 20` |
| E3, empilhadeiras | Tabela 14 | `.venv/bin/python validar.py varredura --processo processos/recebimento_saderova.yaml --variante exp2 --pool empilhadeira --de 1 --ate 4 --replicas 20` |
| E4, conferentes | Tabela 15 | `.venv/bin/python validar.py varredura --processo processos/recebimento_saderova.yaml --variante exp2 --pool conferente --de 8 --ate 20 --replicas 20` |
| E5, intervenções no turnaround | Tabela 16 | `.venv/bin/python validar.py intervencoes` (200 réplicas) |
| E7, alocação (a Tabela 17 foi gerada com **5 réplicas**) | Tabela 17 | `.venv/bin/python validar.py otimizar --processo processos/recebimento_saderova.yaml --variante exp2 --limite-espera 120 --replicas 5` e o mesmo com `--limite-espera 200` |
| E7, recozimento com as sementes 1000 a 1009 | Seção 4.1.5 | os mesmos comandos, com `--sa-sementes 10` (limites de 120 e de 200) |
| E8, linha de montagem | Seção 4.1.6 | `.venv/bin/python validar.py salbp --arquivo processos/salbp/P25_14_ROSZIEG.alb --otimo 10` |
| E9, escalabilidade | Figura 14 | `.venv/bin/python validar.py escalabilidade` (não rode se quiser manter os CSVs do texto: os tempos dependem da máquina) |

Para conferir tudo de uma vez contra os números do texto (não grava nada em `resultados/`):

```bash
.venv/bin/python conferir_texto.py             # conferências rápidas
.venv/bin/python conferir_texto.py --completo  # inclui a Tabela 17 e o recozimento com 10 sementes
```

Depois de rodar, `gerar_graficos.py` refaz as figuras de `resultados/graficos/` e
`gerar_excel_escalabilidade.py` refaz `resultados/escalabilidade.xlsx`.
Os tempos de execução dependem da máquina; os demais resultados são idênticos para a mesma semente.

## Estrutura

```
app.py                     página principal (modelos M1–M3)
pages/1_Processos_reais.py página dos modelos M4 e M5
style.css, .streamlit/     visual e temas claro/escuro
validar.py                 linha de comando dos experimentos
conferir_texto.py          confere o programa contra os números do texto
gerar_graficos.py          figuras a partir dos CSVs
gerar_excel_escalabilidade.py  planilha de escalabilidade
processos/                 processos em YAML e instâncias SALBP
resultados/                CSVs, figuras e planilhas geradas
tests/                     testes (pytest)
src/
  domain.py, rede.py, simulacao.py, analise.py   modelos base M1–M3
  processo.py      distribuições, trabalhadores, atividades e leitura do YAML
  motor.py         simulação SimPy genérica (junção AND, trabalhadores com nome)
  estrutural.py    capacidade por grupo, caminho crítico (CPM) e corte mínimo (Edmonds-Karp)
  replicacoes.py   réplicas, IC 95% e varredura do nº de trabalhadores
  otimizacao.py    alocação: busca exaustiva, gulosa e recozimento simulado
  filas.py         filas M/M/c com fórmula conhecida (Tabela 6)
  salbp.py         leitura de instâncias SALBP e atribuição de estações
  escalabilidade.py processos sintéticos para medir tempo e memória
  grafo_processo.py desenho do grafo dos processos reais
  ui.py            cards, gráficos e temas
```
