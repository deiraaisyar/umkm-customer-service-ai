FROM python:3.12-slim

WORKDIR /app

# Install dependencies (CPU-only torch via requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy entire project (includes pre-built data/chroma/ and data/bot.db)
COPY . .

# Entrypoint just starts the service directly — no setup needed at runtime
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "bot.main"]
