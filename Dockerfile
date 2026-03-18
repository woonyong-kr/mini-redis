FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 복사 (레이어 캐싱 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

EXPOSE 6379

CMD ["python", "server.py"]
