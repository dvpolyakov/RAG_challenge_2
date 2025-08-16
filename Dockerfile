FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for building wheels and faiss-cpu runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python deps first (better layer caching)
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project sources
COPY setup.py ./
COPY src ./src
COPY main.py ./
COPY docs ./docs

# Install editable package
RUN pip install -e .

# Default command prints CLI help
CMD ["python", "main.py", "--help"]


