# UMKM Customer Service AI

An AI-powered customer service solution tailored for Small and Medium Enterprises (UMKMs). The system integrates a Telegram bot for automated customer interactions and a Streamlit dashboard for real-time analytics.

## Demo

[Watch Video Demo on Google Drive](https://drive.google.com/drive/folders/1nWqFcKYsf8AFRjgJt9zUN291mQiAqVcz?usp=sharing)

## Live Deployment
*   **Telegram Bot**: [@NMCSDEMOBot](https://t.me/NMCSDEMOBot)
*   **Analytics Dashboard**: [http://35.254.192.4:8501/](http://35.254.192.4:8501/)

## Core Features

*   **Intelligent Conversational Agent**: Utilizes Google Gemini LLM to handle customer inquiries, process orders, and provide contextual responses.
*   **Semantic & Visual Search**: Implements ChromaDB and `clip-ViT-B-32` (via Sentence-Transformers) to enable product retrieval through both text queries and image uploads.
*   **Analytics Dashboard**: A Streamlit interface to monitor conversation volume, sentiment, user ratings, and latency metrics.
*   **Containerized Deployment**: Packaged with Docker and Docker Compose for reliable execution across local and cloud environments (e.g., Google Cloud Platform).

## Tech Stack

*   **Language**: Python 3.12
*   **AI/ML**: Google Generative AI (Gemini), PyTorch (CPU), Sentence-Transformers
*   **Database**: SQLite (Transactional), ChromaDB (Vector Search)
*   **Frontend**: Streamlit, Plotly
*   **Infrastructure**: Docker, Docker Compose

## Setup and Deployment

### Prerequisites
*   Docker and Docker Compose installed.
*   Telegram Bot Token (via BotFather).
*   Google Gemini API Key.

### Environment Configuration
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_telegram_token_here
GCP_API_KEY=your_gemini_api_key_here
```

### Running the Services
The application is pre-configured to use pre-built Docker images hosted on Docker Hub. To start the services, run:

```bash
docker compose up -d
```

This will spin up two containers:
1.  **nappa-bot**: The background Telegram bot service.
2.  **nappa-dashboard**: The analytics interface, accessible at `http://localhost:8501`.

### Data Initialization
The current Docker images contain a pre-indexed ChromaDB and SQLite schema. If you update the product catalog (`data/products.csv`), you must regenerate the database locally before rebuilding the image:

```bash
python3 setup_db.py
```
