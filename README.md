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
