FROM python:3.12-slim



WORKDIR /app

# Install the rest of the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy entire project
COPY . .

# Entrypoint: runs setup_db.py on first boot, then starts the service
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "bot.main"]
