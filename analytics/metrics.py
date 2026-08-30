from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


class MarketAnalytics:
    """Módulo de inteligência analítica de mercado automotivo"""

    @staticmethod
    def calcular_radar_oportunidades(df: pd.DataFrame, min_amostras: int = 3, margem_desconto_min: float = 0.05) -> pd.DataFrame:
        """
        Identifica barganhas comparando o preço do veículo com a média
        de mercado para a mesma Marca + Modelo + Ano Modelo.
        """
        if df.empty:
            return pd.DataFrame()

        df_calc = df.copy()

        # Agrupar por Marca, Modelo e Ano para calcular referência
        grupo = ["marca", "modelo", "ano_modelo"]
        stats = (
            df_calc.groupby(grupo)
            .agg(
                preco_medio_categoria=("preco", "mean"),
                preco_mediano_categoria=("preco", "median"),
                km_media_categoria=("quilometragem", "mean"),
                total_amostras=("preco", "count"),
            )
            .reset_index()
        )

        # Filtrar categorias com amostras suficientes para significância estatística
        stats = stats[stats["total_amostras"] >= min_amostras]

        df_merged = pd.merge(df_calc, stats, on=grupo, how="inner")

        # Calcular desconto relativo à média (%)
        df_merged["diferenca_valor"] = df_merged["preco_medio_categoria"] - df_merged["preco"]
        df_merged["desconto_percentual"] = (df_merged["diferenca_valor"] / df_merged["preco_medio_categoria"]) * 100

        # Score de Oportunidade: combina desconto percentual com quilometragem abaixo da média
        df_merged["km_ratio"] = np.where(
            df_merged["km_media_categoria"] > 0,
            df_merged["quilometragem"] / df_merged["km_media_categoria"],
            1.0,
        )
        
        # Filtra apenas veículos com desconto acima da margem mínima
        oportunidades = df_merged[df_merged["desconto_percentual"] >= (margem_desconto_min * 100)]
        return oportunidades.sort_values(by="desconto_percentual", ascending=False)

    @staticmethod
    def curva_depreciacao(df: pd.DataFrame, marca: str, modelo: str) -> pd.DataFrame:
        """
        Retorna a curva de preço médio por ano do modelo especificado.
        """
        df_filtro = df[(df["marca"].str.upper() == marca.upper()) & (df["modelo"].str.upper() == modelo.upper())]
        if df_filtro.empty:
            return pd.DataFrame()

        curva = (
            df_filtro.groupby("ano_modelo")
            .agg(
                preco_medio=("preco", "mean"),
                preco_min=("preco", "min"),
                preco_max=("preco", "max"),
                km_media=("quilometragem", "mean"),
                total_veiculos=("preco", "count"),
            )
            .reset_index()
            .sort_values("ano_modelo")
        )
        return curva

    @staticmethod
    def resumo_regional(df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera resumo estatístico agrupado por estado (UF).
        """
        if df.empty or "estado" not in df.columns:
            return pd.DataFrame()

        df_calc = df.copy()
        # Normalizar UF (extrair sigla de 2 letras ou manter limpo)
        df_calc["uf_sigla"] = df_calc["estado"].str.extract(r"\(([A-Z]{2})\)")[0].fillna(df_calc["estado"])
        
        regional = (
            df_calc.groupby("uf_sigla")
            .agg(
                total_veiculos=("preco", "count"),
                preco_medio=("preco", "mean"),
                km_media=("quilometragem", "mean"),
                marcas_distintas=("marca", "nunique"),
                modelos_distintos=("modelo", "nunique"),
            )
            .reset_index()
            .sort_values("total_veiculos", ascending=False)
        )
        return regional

    @staticmethod
    def calcular_arbitragem_interestadual(
        df: pd.DataFrame, min_amostras_uf: int = 1
    ) -> pd.DataFrame:
        """
        Identifica oportunidades de arbitragem interestadual:
        Compara o preço médio do mesmo veículo (Marca + Modelo + Ano)
        entre diferentes estados, apontando onde comprar mais barato e vender mais caro.
        """
        if df.empty or "estado" not in df.columns:
            return pd.DataFrame()

        df_calc = df.copy()
        df_calc["uf_sigla"] = df_calc["estado"].str.extract(r"\(([A-Z]{2})\)")[0].fillna(df_calc["estado"])

        grupo_uf = ["marca", "modelo", "ano_modelo", "uf_sigla"]
        stats_uf = (
            df_calc.groupby(grupo_uf)
            .agg(preco_medio=("preco", "mean"), qtd=("preco", "count"))
            .reset_index()
        )
        stats_uf = stats_uf[stats_uf["qtd"] >= min_amostras_uf]

        # Agrupar por veículo para ver se há pelo menos 2 estados
        grupo_veiculo = ["marca", "modelo", "ano_modelo"]
        contagem_ufs = stats_uf.groupby(grupo_veiculo)["uf_sigla"].nunique().reset_index()
        veiculos_multistate = contagem_ufs[contagem_ufs["uf_sigla"] >= 2][grupo_veiculo]

        if veiculos_multistate.empty:
            return pd.DataFrame()

        dados_filtrados = pd.merge(stats_uf, veiculos_multistate, on=grupo_veiculo, how="inner")

        linhas = []
        for (marca, modelo, ano), grp in dados_filtrados.groupby(grupo_veiculo):
            idx_min = grp["preco_medio"].idxmin()
            idx_max = grp["preco_medio"].idxmax()

            row_min = grp.loc[idx_min]
            row_max = grp.loc[idx_max]

            preco_min = row_min["preco_medio"]
            preco_max = row_max["preco_medio"]
            uf_barata = row_min["uf_sigla"]
            uf_cara = row_max["uf_sigla"]

            if uf_barata != uf_cara and preco_min > 0:
                spread = preco_max - preco_min
                spread_pct = (spread / preco_min) * 100
                if spread >= 1000.0:  # Mínimo de R$ 1.000 de diferença
                    linhas.append(
                        {
                            "marca": marca,
                            "modelo": modelo,
                            "ano_modelo": ano,
                            "uf_menor_preco": uf_barata,
                            "preco_menor": preco_min,
                            "uf_maior_preco": uf_cara,
                            "preco_maior": preco_max,
                            "spread_reais": spread,
                            "spread_percentual": spread_pct,
                        }
                    )

        if not linhas:
            return pd.DataFrame()

        df_arb = pd.DataFrame(linhas)
        return df_arb.sort_values(by="spread_reais", ascending=False)

