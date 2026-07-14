import io
import pandas as pd
from typing import Dict, Any, List
from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao

class AnalisadorResultados:
    def __init__(self, logs_detalhados: List[Dict[str, Any]], linha: LinhaProducao, resultado: ResultadoSimulacao):
        self.df = pd.DataFrame(logs_detalhados)
        self.linha = linha
        self.resultado = resultado

    def obter_estatisticas(self) -> Dict[str, Dict[str, Any]]:
        estatisticas = {}
        if self.df.empty:
            return estatisticas

        for estacao_id in self.linha.nos.keys():
            df_est = self.df[self.df["estacao"] == estacao_id]
            if df_est.empty:
                continue

            chegadas = df_est[df_est["evento"] == "chegada_fila"].set_index("palete_id")["tempo"]
            inicios = df_est[df_est["evento"] == "inicio_processamento"].set_index("palete_id")["tempo"]
            tempos_espera = (inicios - chegadas).dropna()
            
            espera_media = tempos_espera.mean() if not tempos_espera.empty else 0.0
            espera_max = tempos_espera.max() if not tempos_espera.empty else 0.0
            
            saidas = df_est[df_est["evento"] == "saida_estacao"].set_index("palete_id")["tempo"]
            duracoes = (saidas - inicios).dropna()
            tempo_ativo = duracoes.sum()
            
            tempo_total = self.df["tempo"].max()
            cap = self.linha.nos[estacao_id].capacidade_interna
            utilizacao = (tempo_ativo / (tempo_total * cap)) * 100 if tempo_total > 0 else 0.0
            utilizacao = min(100.0, utilizacao)

            estatisticas[estacao_id] = {
                "espera_media": espera_media,
                "espera_max": espera_max,
                "utilizacao": utilizacao,
                "fila_maxima": df_est["tamanho_fila"].max() if not df_est.empty else 0
            }
        return estatisticas

    def gerar_excel(self) -> bytes:
        output = io.BytesIO()
        
        df_resumo = pd.DataFrame({
            "Métrica": [
                "Topologia da Fábrica",
                "Volume Total de Lotes",
                "Gargalo Dinâmico Detectado",
                "Lotes com Espera na Fila",
                "Tempo Médio de Espera",
                "Tempo Máximo de Espera",
                "Tempo de Execução da Simulação (ms)",
                "Pico de RAM Consumido (KB)"
            ],
            "Valor": [
                self.linha.preset.upper(),
                self.resultado.paletes_entregues,
                "SIM" if self.resultado.gargalo_ativado else "NÃO",
                self.resultado.paletes_com_espera,
                f"{self.resultado.tempo_medio_espera:.4f}",
                f"{self.resultado.tempo_max_espera:.4f}",
                f"{self.resultado.tempo_execucao_seg * 1000:.2f}",
                f"{self.resultado.pico_memoria_kb:.2f}"
            ]
        })

        estats = self.obter_estatisticas()
        estacoes_data = []
        for est_id, metrica in estats.items():
            estacoes_data.append({
                "Estação": est_id,
                "Nome Operacional": self.linha.nos[est_id].rotulo.replace('\n', ' '),
                "Capacidade": self.linha.nos[est_id].capacidade_interna,
                "Utilização (%)": f"{metrica['utilizacao']:.2f}%",
                "Fila Máxima (Lotes)": metrica["fila_maxima"],
                "Espera Média (u.t.)": f"{metrica['espera_media']:.4f}",
                "Espera Máxima (u.t.)": f"{metrica['espera_max']:.4f}"
            })
        df_estacoes = pd.DataFrame(estacoes_data)

        df_logs = self.df.copy()
        
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_resumo.to_excel(writer, sheet_name="Resumo Geral", index=False)
            df_estacoes.to_excel(writer, sheet_name="Desempenho por Estação", index=False)
            df_logs.to_excel(writer, sheet_name="Logs de Eventos", index=False)

        return output.getvalue()
