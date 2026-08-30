-- Tabela principal de veículos anunciados
CREATE TABLE IF NOT EXISTS anuncios (
    id_anuncio VARCHAR PRIMARY KEY,
    marca VARCHAR NOT NULL,
    modelo VARCHAR NOT NULL,
    versao VARCHAR,
    ano_fabricacao INTEGER,
    ano_modelo INTEGER,
    quilometragem DOUBLE,
    preco DOUBLE NOT NULL,
    cidade VARCHAR,
    estado VARCHAR,
    tipo_vendedor VARCHAR,
    url_anuncio VARCHAR,
    foto_url VARCHAR,
    data_primeira_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_ultima_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR DEFAULT 'ATIVO'
);

-- Sequência para IDs de histórico de preços
CREATE SEQUENCE IF NOT EXISTS seq_historico START 1;

-- Tabela de histórico de alterações de preços dos anúncios
CREATE TABLE IF NOT EXISTS historico_precos (
    id_historico BIGINT PRIMARY KEY DEFAULT nextval('seq_historico'),
    id_anuncio VARCHAR NOT NULL,
    preco_anterior DOUBLE NOT NULL,
    preco_novo DOUBLE NOT NULL,
    data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de logs e metadados de execução do crawler
CREATE TABLE IF NOT EXISTS execucoes_crawler (
    id_execucao VARCHAR PRIMARY KEY,
    data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_fim TIMESTAMP,
    uf VARCHAR,
    marca VARCHAR,
    total_anuncios_processados INTEGER DEFAULT 0,
    novos_anuncios INTEGER DEFAULT 0,
    anuncios_atualizados INTEGER DEFAULT 0,
    status VARCHAR
);
