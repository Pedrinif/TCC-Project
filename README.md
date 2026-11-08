# ⚡ OptiGraph
### Otimização de Fluxo em Redes Logísticas Industriais

> **Pedro Nassif — Trabalho de Graduação (TG)**  
> Pesquisa Operacional · Teoria dos Grafos · Simulação de Eventos Discretos (DES)

---

## ▶️ Como abrir o programa (toda vez que quiser usar)

### Passo 1 — Abra o Terminal
No Mac: pressione **⌘ + Espaço**, digite **Terminal** e aperte Enter.

### Passo 2 — Cole esse comando e aperte Enter

```bash
cd /Users/pedronassif/Documents/Projetos/TCC-Project && .venv/bin/streamlit run app.py
```

### Passo 3 — Abra o navegador

O terminal vai mostrar uma mensagem assim:

```
Local URL: http://localhost:8501
```

Abra o **Google Chrome** (ou Safari) e acesse:

```
http://localhost:8501
```

### Passo 4 — Para fechar o programa

Volte no Terminal e pressione **Ctrl + C**.

---

## 🎮 Como usar o dashboard

### Barra lateral (esquerda)

**1. 🗺️ Topologia do Grafo G=(V,E)**
- Escolha uma das 3 topologias disponíveis:

| Topologia | Nós | Arestas | Descrição |
|-----------|-----|---------|-----------|
| 🔹 **Simples** | 4 | 3 | Doca → Triagem → 2 Estoques |
| 🔷 **Múltiplas Docas** | 6 | 5 | 2 Docas → Hub Central → 3 Estoques |
| 🔶 **Pipeline** | 5 | 4 | Doca → Inspeção → Triagem → 2 Estoques |

**2. 📦 Volume Total de Paletes**
- Controla quantos paletes serão simulados (de 10 a 1.000).

**3. 🔗 Capacidade da Aresta Crítica**
- Define o limite máximo de fluxo na aresta crítica de cada preset.

---

## 📁 Estrutura de Diretórios (Modularizada)

```
TCC-Project/
├── app.py                  # Ponto de entrada (UI Streamlit & Roteamento)
├── style.css               # Estilos CSS customizados (Premium UI)
├── requirements.txt        # Dependências atualizadas (com openpyxl)
├── README.md               # Este guia
└── src/
    ├── __init__.py         # Inicializador do pacote
    ├── domain.py           # Dataclasses de domínio (EstacaoTrabalho, Aresta, ResultadoSimulacao)
    ├── rede.py             # Grafo (NetworkX, Edmonds-Karp/Corte Mínimo, Caminhos)
    ├── simulacao.py        # Simulação estocástica (SimPy + Poisson + Normal)
    └── analise.py          # Relatórios estatísticos e Exportação Excel (.xlsx)
```

---

## 💾 Relatório Multi-Abas em Excel (.xlsx)

O sistema conta com um analisador em Pandas que permite gerar relatórios consolidados em Excel:
- **Resumo Geral**: Métricas operacionais agregadas, gargalo estrutural teórico e throughput computacional.
- **Desempenho por Estação**: Taxas de utilização, tempo máximo de fila e tempo médio de processamento de cada estação de trabalho.
- **Logs de Eventos**: Log de eventos bruto para auditoria de tempo e filas.

---

## 🧱 Motor v2: processos como dados (workers, DAG de atividades e réplicas)

Além do app Streamlit (presets de armazém), o projeto agora tem um motor genérico em que cada
processo real é um arquivo YAML em `processos/`, com a **fonte citada** e as **premissas** explícitas.

```
processos/
├── recebimento_saderova.yaml   # recebimento de paletes (Saderova et al., 2022)
├── turnaround_b737.yaml        # turnaround de avião (San Antonio et al., 2017)
└── salbp/exemplo_didatico.in2  # exemplo INVENTADO para teste; baixe as instâncias reais de assembly-line-balancing.de
src/
├── processo.py     # Distribuições, Trabalhador (pool), Atividade (com precedências) e leitor de YAML
├── motor.py        # Motor SimPy genérico: atividades em paralelo (junção AND), trabalhadores com nome (A_1, A_2...), caminho crítico empírico
├── grafo_processo.py # Nós e arestas do grafo interativo (atividades + trabalhadores, cores por utilização e gargalo)
├── estrutural.py   # Capacidade por pool, CPM (caminho crítico e folgas) e corte mínimo com separação de nós
├── replicacoes.py  # Réplicas independentes, IC 95% e varredura do nº de trabalhadores
└── salbp.py        # Leitor de instâncias SALBP, heurística de atribuição de estações e conversão em Processo
pages/1_Processos_reais.py  # Interface: grafo interativo, trabalhadores, resultados, estrutura e varredura
validar.py          # Comparação com os números publicados (CLI)
tests/              # pytest: M/M/1 e M/M/c contra fórmulas, Lei de Little, DAG, SALBP, YAML
```

```bash
pip install -r requirements.txt
pytest                                   # todos os testes
python validar.py recebimento            # compara com os 3 experimentos do artigo
python validar.py turnaround             # compara com as Tabelas 1 e 2 do artigo
python validar.py salbp --arquivo processos/salbp/exemplo_didatico.in2 --ciclo 10
python validar.py varredura --processo processos/recebimento_saderova.yaml --variante exp2 \
       --pool empilhadeira --de 1 --ate 4 --limite-espera 120
```

### Interface gráfica dos processos reais
```bash
streamlit run app.py
```
No menu lateral, abra **Processos reais**. Escolha o processo, mude a quantidade de cada trabalhador
(2 empilhadeiras viram `empilhadeira_1` e `empilhadeira_2` no grafo), ajuste tempos e clique em
**Executar simulação**: o grafo passa a mostrar a utilização (verde/amarelo/vermelho), o gargalo dinâmico
(borda vermelha) e o estrutural (borda laranja). A aba **Quantos trabalhadores?** faz a varredura com IC de 95%.

Para modelar um processo novo, copie um YAML de `processos/`, troque trabalhadores, atividades
(`predecessoras`) e distribuições (`constante`, `uniforme`, `triangular`, `normal`, `exponencial`,
`weibull`, `lognormal`, `soma`) e preencha `fonte` e `premissas`.
