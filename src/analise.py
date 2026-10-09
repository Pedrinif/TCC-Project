import io
import pandas as pd
from typing import Dict, Any, List
from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao


class AnalisadorResultados:
    """Transforma os logs da simulação em estatísticas por estação e no relatório Excel."""

    def __init__(self, logs_detalhados: List[Dict[str, Any]], linha: LinhaProducao, resultado: ResultadoSimulacao):
        self.df = pd.DataFrame(logs_detalhados)
        self.linha = linha
        self.resultado = resultado

    def obter_estatisticas(self) -> Dict[str, Dict[str, Any]]:
        """
        Para cada estação: espera média/máxima, maior fila e utilização.
        Utilização = tempo ocupado / (tempo total da simulação x capacidade da estação).
        """
        if self.df.empty:
            return {}

        tempo_total = self.df["tempo"].max()
        estatisticas = {}
        for estacao_id, no in self.linha.nos.items():
            df_est = self.df[self.df["estacao"] == estacao_id]
            if df_est.empty:
                continue

            # horário de cada evento, indexado pelo palete
            t = {ev: grupo.set_index("palete_id")["tempo"] for ev, grupo in df_est.groupby("evento")}
            chegadas, inicios, saidas = t["chegada_fila"], t["inicio_processamento"], t["saida_estacao"]

            esperas = (inicios - chegadas).dropna()
            tempo_ocupado = (saidas - inicios).dropna().sum()
            utilizacao = tempo_ocupado / (tempo_total * no.capacidade_interna) * 100 if tempo_total > 0 else 0.0

            estatisticas[estacao_id] = {
                "espera_media": esperas.mean() if not esperas.empty else 0.0,
                "espera_max": esperas.max() if not esperas.empty else 0.0,
                "utilizacao": min(100.0, utilizacao),
                "fila_maxima": df_est["tamanho_fila"].max(),
            }
        return estatisticas

    def gerar_excel(self) -> bytes:
        """Planilha com 3 abas: resumo geral, desempenho por estação e todos os eventos."""
        r = self.resultado
        resumo = pd.DataFrame({
            "Métrica": [
                "Topologia", "Volume de paletes", "Gargalo detectado", "Paletes com espera",
                "Tempo médio de espera", "Tempo máximo de espera",
                "Tempo de execução (ms)", "Pico de RAM (KB)",
            ],
            "Valor": [
                self.linha.preset.upper(), r.paletes_entregues, "SIM" if r.gargalo_ativado else "NÃO",
                r.paletes_com_espera, f"{r.tempo_medio_espera:.4f}", f"{r.tempo_max_espera:.4f}",
                f"{r.tempo_execucao_seg * 1000:.2f}", f"{r.pico_memoria_kb:.2f}",
            ],
        })

        estacoes = pd.DataFrame([
            {
                "Estação": est_id,
                "Nome": self.linha.nos[est_id].rotulo.replace("\n", " "),
                "Capacidade": self.linha.nos[est_id].capacidade_interna,
                "Utilização (%)": f"{m['utilizacao']:.2f}",
                "Fila máxima": m["fila_maxima"],
                "Espera média (u.t.)": f"{m['espera_media']:.4f}",
                "Espera máxima (u.t.)": f"{m['espera_max']:.4f}",
            }
            for est_id, m in self.obter_estatisticas().items()
        ])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            resumo.to_excel(writer, sheet_name="Resumo Geral", index=False)
            estacoes.to_excel(writer, sheet_name="Desempenho por Estação", index=False)
            self.df.to_excel(writer, sheet_name="Logs de Eventos", index=False)
        return output.getvalue()
