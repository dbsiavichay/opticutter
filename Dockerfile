FROM python:3.11-slim-buster

WORKDIR /src

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        cargo \
        default-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
COPY requirements_dev.txt .

RUN pip install --no-cache-dir -r requirements_dev.txt

COPY . .

EXPOSE 3000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]
