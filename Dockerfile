FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-local.txt .
COPY requirements-app.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install -r requirements-local.txt
RUN pip install -r requirements-app.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
