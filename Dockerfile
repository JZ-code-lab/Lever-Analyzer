FROM python:3.11-slim

# System dependencies:
#   antiword     — parses legacy .doc (binary Word) resumes
#   build-essential, libxml2-dev, libxslt1-dev — sometimes needed for lxml wheels
#   curl         — health checks / debugging convenience
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        antiword \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so Docker can cache this layer across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application code.
COPY . .

# Render injects $PORT at runtime. Default to 5000 to match local/.streamlit/config.toml.
ENV PORT=5000
EXPOSE 5000

# Shell-form CMD so ${PORT} is expanded at container start.
CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true
