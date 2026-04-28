# ⚡ OptiGraph
### Otimização de Fluxo em Redes Logísticas Industriais

> **Pedro Nassif — Trabalho de Conclusão de Curso**  
> Pesquisa Operacional · Teoria dos Grafos · Simulação de Eventos Discretos

---

## ▶️ Como abrir o programa (toda vez que quiser usar)

### Passo 1 — Abra o Terminal
No Mac: pressione **⌘ + Espaço**, digite **Terminal** e aperte Enter.

### Passo 2 — Cole esse comando e aperte Enter

```bash
streamlit run ~/Desktop/tcc/app.py
```

> Se der erro "command not found", use esse comando alternativo:
> ```bash
> /Users/pedronassif/Library/Python/3.9/bin/streamlit run ~/Desktop/tcc/app.py
> ```

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

Você vai ver dois controles deslizantes:

**1. Volume Total de Paletes**
- Controla quantos paletes serão simulados (de 10 a 1.000).
- **Quanto maior o número → mais carga no sistema → mais chance de gargalo.**
- Exemplo: coloque **300** para estressar o sistema.

**2. Capacidade c(Doca → Triagem)**
- Define o limite máximo de fluxo na aresta crítica do grafo.
- **Quanto menor esse número → mais fácil de criar gargalo.**
- Exemplo: coloque **100** com volume 300 → gargalo garantido.

**Dica rápida para ver o gargalo:**
| Volume | Capacidade | Resultado |
|--------|-----------|-----------|
| 150 | 200 | ✅ Sistema normal |
| 300 | 100 | 🔴 Gargalo ativo |
| 500 | 50 | 🚨 Fila enorme |

---

### Botão "▶ Executar Simulação"

Depois de ajustar os sliders, clique neste botão.  
Aguarde alguns segundos (uma animação de carregamento aparece).

---

### O que aparece depois de executar

**🟡 Banner no topo:**
- Vermelho = gargalo detectado na aresta Doca → Triagem
- Verde = sistema operou dentro da capacidade

**Cards — Visão Operacional:**
| Card | O que significa |
|------|----------------|
| Paletes Entregues | Total de paletes que passaram pelo sistema |
| Paletes com Espera | Quantos ficaram presos na fila da Triagem |
| Tempo Médio na Fila | Média de tempo que cada palete esperou |
| Tempo Máximo de Espera | O pior caso — palete que ficou mais tempo esperando |

**Cards — Visão Estrutural (foco do TCC):**
| Card | O que significa |
|------|----------------|
| Tempo de Execução | Quantos milissegundos o algoritmo demorou para rodar |
| Pico de RAM | Quanto de memória o programa consumiu no pico |
| Throughput | Quantos paletes foram processados por milissegundo |

---

### O Grafo (parte de baixo da tela)

Mostra o mapa do sistema logístico com 4 nós conectados:

```
🚛 Doca → 🔀 Triagem → 📦 Estoque A
                     → 📦 Estoque B
```

**Cores das arestas (setas):**
- 🔵 **Azul** → fluxo normal, dentro da capacidade
- 🔴 **Vermelho** → gargalo! O fluxo atingiu o limite

**Interações no grafo:**
- 🖱️ **Scroll** → zoom in/out
- 🖱️ **Clicar e arrastar** → mover nós
- 🖱️ **Passar o mouse** em cima de um nó ou seta → ver detalhes

---

## 🔁 Fluxo de uso resumido

```
1. Abrir Terminal
      ↓
2. Rodar: streamlit run ~/Desktop/tcc/app.py
      ↓
3. Abrir http://localhost:8501 no navegador
      ↓
4. Ajustar os sliders na sidebar
      ↓
5. Clicar em ▶ Executar Simulação
      ↓
6. Analisar os cards e o grafo
      ↓
7. Mudar os sliders e executar de novo para comparar
```

---

## ⚠️ Problemas comuns

| Problema | Solução |
|----------|---------|
| "command not found: streamlit" | Use o comando alternativo com caminho completo (ver Passo 2) |
| Tela abrindo no Live Server (mostra só o arquivo) | Não use Live Server. Acesse pelo Terminal + `http://localhost:8501` |
| Página em branco no navegador | Aguarde 5 segundos e recarregue com **⌘ + R** |
| Precisa fechar o programa | Pressione **Ctrl + C** no Terminal |
| Quer abrir de novo depois de fechar | Repita os Passos 1 a 3 |

---

## 📁 Arquivos do projeto

```
tcc/
├── app.py       ← código-fonte completo (não edite sem querer)
└── README.md    ← este guia
```

---

## 📚 Sobre o projeto

Este dashboard simula paletes percorrendo um sistema logístico modelado como grafo G=(V,E).  
O objetivo é demonstrar como restrições de capacidade em arestas criam **gargalos mensuráveis**, validando conceitos de **Teoria dos Grafos** e **Pesquisa Operacional** de forma visual e interativa.
