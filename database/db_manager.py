import duckdb
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime

from config.settings import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class DatabaseManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def get_connection(self):
        return duckdb.connect(self.db_path)

    def _init_db(self):
        """Inicializa as tabelas no DuckDB usando o schema.sql"""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql_script = f.read()

        with self.get_connection() as conn:
            conn.execute(sql_script)

    def upsert_anuncios(self, anuncios: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Sincroniza anúncios com o banco de dados:
        - Se o anúncio tem ID novo: insere o registro completo.
        - Se o anúncio já existe e tem qualquer dado diferente do original: atualiza os campos.
        - Se o preço foi modificado: adiciona um registro ao historico_precos.
        - Se todos os dados forem idênticos: apenas atualiza data_ultima_captura e status.
        """
        if not anuncios:
            return {"inseridos": 0, "atualizados": 0, "precos_alterados": 0, "mantidos": 0}

        df_novos = pd.DataFrame(anuncios)
        df_novos["id_anuncio"] = df_novos["id_anuncio"].astype(str).str.strip()
        df_novos["preco"] = pd.to_numeric(df_novos["preco"], errors="coerce").fillna(0.0)
        df_novos["quilometragem"] = pd.to_numeric(df_novos["quilometragem"], errors="coerce").fillna(0.0)
        df_novos["ano_fabricacao"] = pd.to_numeric(df_novos["ano_fabricacao"], errors="coerce").fillna(0).astype(int)
        df_novos["ano_modelo"] = pd.to_numeric(df_novos["ano_modelo"], errors="coerce").fillna(0).astype(int)

        agora = datetime.now()
        df_novos["data_ultima_captura"] = agora
        df_novos["status"] = "ATIVO"

        inseridos = 0
        atualizados = 0
        precos_alterados = 0
        mantidos = 0

        with self.get_connection() as conn:
            # Buscar anúncios já existentes para comparação minuciosa campo a campo
            ids = tuple(df_novos["id_anuncio"].tolist())
            if len(ids) == 1:
                existentes = conn.execute(
                    f"SELECT id_anuncio, preco, quilometragem, versao, cidade, estado, tipo_vendedor, foto_url FROM anuncios WHERE id_anuncio = '{ids[0]}'"
                ).fetchdf()
            else:
                existentes = conn.execute(
                    f"SELECT id_anuncio, preco, quilometragem, versao, cidade, estado, tipo_vendedor, foto_url FROM anuncios WHERE id_anuncio IN {ids}"
                ).fetchdf()

            existentes_map = {}
            if not existentes.empty:
                for _, ex_row in existentes.iterrows():
                    existentes_map[str(ex_row["id_anuncio"])] = {
                        "preco": float(ex_row["preco"] or 0.0),
                        "quilometragem": float(ex_row["quilometragem"] or 0.0),
                        "versao": str(ex_row["versao"] or "").strip(),
                        "cidade": str(ex_row["cidade"] or "").strip(),
                        "estado": str(ex_row["estado"] or "").strip(),
                        "tipo_vendedor": str(ex_row["tipo_vendedor"] or "").strip(),
                        "foto_url": str(ex_row["foto_url"] or "").strip(),
                    }

            for _, row in df_novos.iterrows():
                aid = str(row["id_anuncio"])
                preco_novo = float(row["preco"])
                km_nova = float(row["quilometragem"])
                versao_nova = str(row.get("versao") or "").strip()
                cidade_nova = str(row.get("cidade") or "").strip()
                estado_novo = str(row.get("estado") or "").strip()
                tipo_vend_novo = str(row.get("tipo_vendedor") or "").strip()
                foto_nova = str(row.get("foto_url") or "").strip()

                if aid in existentes_map:
                    antigo = existentes_map[aid]
                    preco_anterior = antigo["preco"]
                    km_anterior = antigo["quilometragem"]
                    versao_anterior = antigo["versao"]
                    cidade_anterior = antigo["cidade"]
                    estado_anterior = antigo["estado"]
                    tipo_anterior = antigo["tipo_vendedor"]
                    foto_anterior = antigo["foto_url"]

                    # Verificar alterações
                    mudou_preco = abs(preco_anterior - preco_novo) > 1.0
                    mudou_km = abs(km_anterior - km_nova) > 1.0
                    mudou_versao = bool(versao_nova) and versao_anterior != versao_nova
                    mudou_cidade = bool(cidade_nova) and cidade_anterior != cidade_nova
                    mudou_estado = bool(estado_novo) and estado_anterior != estado_novo
                    mudou_tipo = bool(tipo_vend_novo) and tipo_anterior != tipo_vend_novo
                    mudou_foto = bool(foto_nova) and foto_anterior != foto_nova

                    if mudou_preco:
                        # Registrar alteração no histórico de preços
                        conn.execute(
                            """
                            INSERT INTO historico_precos (id_historico, id_anuncio, preco_anterior, preco_novo, data_alteracao)
                            VALUES (nextval('seq_historico'), ?, ?, ?, ?)
                            """,
                            [aid, preco_anterior, preco_novo, agora],
                        )
                        precos_alterados += 1

                    if mudou_preco or mudou_km or mudou_versao or mudou_cidade or mudou_estado or mudou_tipo or mudou_foto:
                        # Atualizar campos modificados
                        conn.execute(
                            """
                            UPDATE anuncios
                            SET preco = ?,
                                quilometragem = ?,
                                versao = CASE WHEN ? != '' THEN ? ELSE versao END,
                                cidade = CASE WHEN ? != '' THEN ? ELSE cidade END,
                                estado = CASE WHEN ? != '' THEN ? ELSE estado END,
                                tipo_vendedor = CASE WHEN ? != '' THEN ? ELSE tipo_vendedor END,
                                foto_url = CASE WHEN ? != '' THEN ? ELSE foto_url END,
                                data_ultima_captura = ?,
                                status = 'ATIVO'
                            WHERE id_anuncio = ?
                            """,
                            [
                                preco_novo,
                                km_nova,
                                versao_nova, versao_nova,
                                cidade_nova, cidade_nova,
                                estado_novo, estado_novo,
                                tipo_vend_novo, tipo_vend_novo,
                                foto_nova, foto_nova,
                                agora,
                                aid,
                            ],
                        )
                        atualizados += 1
                    else:
                        # Dados idênticos: atualizar apenas timestamp de captura ativa
                        conn.execute(
                            """
                            UPDATE anuncios
                            SET data_ultima_captura = ?, status = 'ATIVO'
                            WHERE id_anuncio = ?
                            """,
                            [agora, aid],
                        )
                        mantidos += 1
                else:
                    # Anúncio novo: inserir
                    conn.execute(
                        """
                        INSERT INTO anuncios (
                            id_anuncio, marca, modelo, versao, ano_fabricacao, ano_modelo,
                            quilometragem, preco, cidade, estado, tipo_vendedor,
                            url_anuncio, foto_url, data_primeira_captura, data_ultima_captura, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            aid,
                            row.get("marca"),
                            row.get("modelo"),
                            versao_nova,
                            int(row.get("ano_fabricacao", 0)),
                            int(row.get("ano_modelo", 0)),
                            km_nova,
                            preco_novo,
                            cidade_nova,
                            estado_novo,
                            tipo_vend_novo,
                            row.get("url_anuncio"),
                            foto_nova,
                            agora,
                            agora,
                            "ATIVO",
                        ],
                    )
                    inseridos += 1

        return {
            "inseridos": inseridos,
            "atualizados": atualizados,
            "precos_alterados": precos_alterados,
            "mantidos": mantidos,
        }

    def iniciar_execucao(self, id_execucao: str, uf: str = "NACIONAL", marca: str = "TODAS"):
        """Registra o início de uma execução do crawler"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO execucoes_crawler (id_execucao, data_inicio, uf, marca, status)
                VALUES (?, ?, ?, ?, 'EM_ANDAMENTO')
                """,
                [id_execucao, datetime.now(), uf, marca],
            )

    def finalizar_execucao(
        self,
        id_execucao: str,
        total_processados: int,
        novos: int,
        atualizados: int,
        status: str = "SUCESSO",
    ):
        """Atualiza a execução do crawler com as métricas finais"""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE execucoes_crawler
                SET data_fim = ?,
                    total_anuncios_processados = ?,
                    novos_anuncios = ?,
                    anuncios_atualizados = ?,
                    status = ?
                WHERE id_execucao = ?
                """,
                [datetime.now(), total_processados, novos, atualizados, status, id_execucao],
            )

    def get_historico_execucoes(self, limit: int = 10) -> pd.DataFrame:
        """Retorna os logs das últimas execuções"""
        with self.get_connection() as conn:
            return conn.execute(
                f"""
                SELECT id_execucao, data_inicio, data_fim, uf, marca,
                       total_anuncios_processados, novos_anuncios, anuncios_atualizados, status
                FROM execucoes_crawler
                ORDER BY data_inicio DESC
                LIMIT {limit}
                """
            ).fetchdf()

    def get_dataframe(self, query: str = "SELECT * FROM anuncios") -> pd.DataFrame:
        """Executa uma query analítica e retorna como Pandas DataFrame"""
        with self.get_connection() as conn:
            return conn.execute(query).fetchdf()

    def get_metricas_gerais(self) -> Dict[str, Any]:
        """Retorna resumo estatístico da base"""
        with self.get_connection() as conn:
            res = conn.execute(
                """
                SELECT 
                    count(*) as total_veiculos,
                    count(distinct marca) as total_marcas,
                    count(distinct modelo) as total_modelos,
                    round(avg(preco), 2) as preco_medio,
                    round(avg(quilometragem), 2) as km_media,
                    min(preco) as menor_preco,
                    max(preco) as maior_preco
                FROM anuncios
                WHERE status = 'ATIVO'
                """
            ).fetchone()

        if not res or res[0] == 0:
            return {
                "total_veiculos": 0,
                "total_marcas": 0,
                "total_modelos": 0,
                "preco_medio": 0,
                "km_media": 0,
                "menor_preco": 0,
                "maior_preco": 0,
            }

        return {
            "total_veiculos": res[0],
            "total_marcas": res[1],
            "total_modelos": res[2],
            "preco_medio": res[3],
            "km_media": res[4],
            "menor_preco": res[5],
            "maior_preco": res[6],
        }
