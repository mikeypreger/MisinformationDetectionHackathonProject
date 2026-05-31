FROM python:3.13-slim

WORKDIR /app

# Install Node.js 20 for the Vite frontend build
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first — Railway has no GPU and CUDA wheels are 3x larger
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy English model
RUN python -m spacy download en_core_web_sm

# Build React frontend
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm install
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Copy application source
COPY . .

ENV DEV_MODE=False

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
