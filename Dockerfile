FROM python:3.11-slim

WORKDIR /app

# Instalar dependências básicas de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação e preservar seed do banco de dados
COPY . .
RUN mkdir -p seed_data && if [ -f data/webmotors.duckdb ]; then cp data/webmotors.duckdb seed_data/webmotors.duckdb; fi

# Garantir diretório de dados
RUN mkdir -p data

EXPOSE 8501

CMD ["streamlit", "run", "app/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
