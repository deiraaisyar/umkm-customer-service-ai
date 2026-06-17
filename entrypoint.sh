#!/bin/bash
set -e

# Run DB setup on first boot (creates SQLite tables + indexes ChromaDB products)
if [ ! -f /app/data/bot.db ]; then
    echo "==> First boot: running setup_db.py ..."
    python3 setup_db.py
    echo "==> Setup complete."
fi

# Execute the command passed to this container (bot or dashboard)
exec "$@"
