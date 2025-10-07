# Руководство по развертыванию

## Обзор

Данное руководство описывает процесс развертывания RAG-системы для edna Chat Center в различных средах: от локальной разработки до production.

## Требования к системе

### Минимальные требования
- **CPU**: 4 ядра
- **RAM**: 8 GB
- **Storage**: 10 GB свободного места
- **Network**: Стабильное интернет-соединение
- **OS**: Linux (Ubuntu 20.04+), macOS, Windows 10+

### Рекомендуемые требования
- **CPU**: 8+ ядер
- **RAM**: 16+ GB
- **Storage**: 50+ GB SSD
- **Network**: 100+ Mbps
- **OS**: Ubuntu 22.04 LTS

## Локальная разработка

### 1. Подготовка окружения

```bash
# Клонирование репозитория
git clone <repository-url>
cd RAG_clean

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка конфигурации

```bash
# Копирование конфигурации
cp env.example .env

# Редактирование конфигурации
nano .env
```

**Минимальная конфигурация для разработки:**
```env
# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key

# YandexGPT (обязательно)
YANDEX_API_KEY=your_yandex_key
YANDEX_CATALOG_ID=your_catalog_id

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# Остальные настройки можно оставить по умолчанию
```

### 3. Запуск зависимостей

#### Qdrant (Docker)
```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

#### Sparse Embeddings Service (опционально)
```bash
cd sparse_service
python app.py
```

### 4. Инициализация системы

```bash
# Инициализация Qdrant
python scripts/init_qdrant.py

# Индексация документации (v4.2.0)
python -m ingestion.run --source docusaurus --docs-root "C:\CC_RAG\docs"

# Полная переиндексация с очисткой коллекции
python -m ingestion.run --source docusaurus --docs-root "C:\CC_RAG\docs" --clear-collection

# Индексация с ограничением количества документов (для тестирования)
python -m ingestion.run --source docusaurus --docs-root "C:\CC_RAG\docs" --max-pages 10
```

### 5. Запуск приложения

```bash
# Terminal 1: Flask API
python wsgi.py

# Terminal 2: Telegram Bot
python adapters/telegram/polling.py
```

## Docker развертывание

### 1. Docker Compose

Создайте файл `docker-compose.yml`:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334

  rag-api:
    build: .
    ports:
      - "9000:9000"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - YANDEX_API_KEY=${YANDEX_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    depends_on:
      - qdrant
    volumes:
      - ./logs:/app/logs

  telegram-bot:
    build: .
    command: python adapters/telegram_polling.py
    environment:
      - QDRANT_URL=http://qdrant:6333
      - YANDEX_API_KEY=${YANDEX_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    depends_on:
      - rag-api
    volumes:
      - ./logs:/app/logs

volumes:
  qdrant_data:
```

### 2. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание пользователя
RUN useradd -m -u 1000 raguser && chown -R raguser:raguser /app
USER raguser

# Создание директории для логов
RUN mkdir -p /app/logs

# Экспорт порта
EXPOSE 9000

# Команда по умолчанию
CMD ["python", "wsgi.py"]
```

### 3. Запуск

```bash
# Создание .env файла
cp env.example .env
# Отредактируйте .env с вашими ключами

# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## Production развертывание

### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Конфигурация для production

Создайте файл `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  rag-api:
    build: .
    ports:
      - "9000:9000"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - YANDEX_API_KEY=${YANDEX_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - FLASK_ENV=production
    depends_on:
      - qdrant
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G

  telegram-bot:
    build: .
    command: python adapters/telegram_polling.py
    environment:
      - QDRANT_URL=http://qdrant:6333
      - YANDEX_API_KEY=${YANDEX_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    depends_on:
      - rag-api
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - rag-api
    restart: unless-stopped

volumes:
  qdrant_data:
```

### 3. Nginx конфигурация

Создайте файл `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream rag_api {
        server rag-api:9000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location / {
            proxy_pass http://rag_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://rag_api/v1/admin/health;
            access_log off;
        }
    }
}
```

### 4. SSL сертификаты

```bash
# Используя Let's Encrypt
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Копирование сертификатов
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/key.pem
sudo chown $USER:$USER ./ssl/*
```

### 5. Запуск production

```bash
# Создание production .env
cp env.example .env.prod
# Настройте production переменные

# Запуск
docker-compose -f docker-compose.prod.yml up -d

# Проверка статуса
docker-compose -f docker-compose.prod.yml ps
```

## Kubernetes развертывание

### 1. Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rag-system
```

### 2. ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rag-config
  namespace: rag-system
data:
  QDRANT_URL: "http://qdrant:6333"
  FLASK_ENV: "production"
```

### 3. Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-secrets
  namespace: rag-system
type: Opaque
data:
  YANDEX_API_KEY: <base64-encoded-key>
  TELEGRAM_BOT_TOKEN: <base64-encoded-token>
```

### 4. Qdrant Deployment

```yaml
# k8s/qdrant.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
  namespace: rag-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
      - name: qdrant
        image: qdrant/qdrant:latest
        ports:
        - containerPort: 6333
        env:
        - name: QDRANT__SERVICE__HTTP_PORT
          value: "6333"
        resources:
          requests:
            memory: "2Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: qdrant
  namespace: rag-system
spec:
  selector:
    app: qdrant
  ports:
  - port: 6333
    targetPort: 6333
```

### 5. RAG API Deployment

```yaml
# k8s/rag-api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api
  namespace: rag-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-api
  template:
    metadata:
      labels:
        app: rag-api
    spec:
      containers:
      - name: rag-api
        image: your-registry/rag-system:latest
        ports:
        - containerPort: 9000
        envFrom:
        - configMapRef:
            name: rag-config
        - secretRef:
            name: rag-secrets
        resources:
          requests:
            memory: "4Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /v1/admin/health
            port: 9000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /v1/admin/health
            port: 9000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: rag-api
  namespace: rag-system
spec:
  selector:
    app: rag-api
  ports:
  - port: 9000
    targetPort: 9000
  type: ClusterIP
```

### 6. Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rag-ingress
  namespace: rag-system
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: rag-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: rag-api
            port:
              number: 9000
```

### 7. Применение манифестов

```bash
# Применение всех манифестов
kubectl apply -f k8s/

# Проверка статуса
kubectl get pods -n rag-system
kubectl get services -n rag-system
kubectl get ingress -n rag-system
```

## Мониторинг и логирование

### 1. Быстрый запуск мониторинга

```bash
# Запуск Grafana + Prometheus
.\start_monitoring.ps1

# Доступ к интерфейсам
# Prometheus: http://localhost:9090
# Grafana: http://localhost:8080 (admin/admin123)
```

### 2. Docker Compose мониторинг

```bash
# Запуск только мониторинга
docker-compose -f docker-compose.monitoring.yml up -d

# Проверка статуса
docker ps | grep -E "(prometheus|grafana)"
```

### 3. Prometheus конфигурация

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'rag-api'
    static_configs:
      - targets: ['172.17.0.1:9001']  # Windows WSL
    scrape_interval: 5s
    metrics_path: '/metrics'
```

### 4. Grafana дашборды

Система автоматически создает готовый дашборд "RAG System Overview" с визуализацией:

- **Query Performance** — производительность запросов и этапов обработки
- **Cache Analytics** — эффективность кэширования
- **Error Monitoring** — мониторинг ошибок и их типов
- **System Health** — общее состояние системы

```bash
# Доступ к Grafana
# URL: http://localhost:8080
# Login: admin
# Password: admin123
```

### 5. Логирование

```yaml
# logging/fluentd.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/*rag*.log
      pos_file /var/log/fluentd-containers.log.pos
      tag kubernetes.*
      format json
    </source>

    <match kubernetes.**>
      @type elasticsearch
      host elasticsearch.logging.svc.cluster.local
      port 9200
      index_name rag-logs
    </match>
```

### 3. Health Checks

```bash
# Проверка здоровья системы
curl http://localhost:9000/v1/admin/health

# Проверка метрик
curl http://localhost:9000/metrics
```

## Backup и восстановление

### 1. Backup Qdrant

```bash
# Создание backup
docker exec qdrant qdrant-cli snapshot create --collection edna_docs

# Копирование backup
docker cp qdrant:/qdrant/snapshots/ ./backups/
```

### 2. Backup конфигурации

```bash
# Backup .env файлов
cp .env .env.backup

# Backup Docker volumes
docker run --rm -v qdrant_data:/data -v $(pwd):/backup alpine tar czf /backup/qdrant_backup.tar.gz -C /data .
```

### 3. Восстановление

```bash
# Восстановление Qdrant
docker run --rm -v qdrant_data:/data -v $(pwd):/backup alpine tar xzf /backup/qdrant_backup.tar.gz -C /data

# Восстановление конфигурации
cp .env.backup .env
```

## Troubleshooting

### Частые проблемы

#### 1. Проблемы с памятью
```bash
# Проверка использования памяти
docker stats

# Увеличение лимитов
docker-compose up -d --scale rag-api=2
```

#### 2. Проблемы с сетью
```bash
# Проверка подключения
docker exec rag-api ping qdrant

# Проверка портов
netstat -tlnp | grep 9000
```

#### 3. Проблемы с логами
```bash
# Просмотр логов
docker-compose logs -f rag-api

# Очистка логов
docker system prune -f
```

### Полезные команды

```bash
# Перезапуск сервисов
docker-compose restart rag-api

# Масштабирование
docker-compose up -d --scale rag-api=3

# Обновление образов
docker-compose pull
docker-compose up -d

# Очистка системы
docker system prune -a
```

## Безопасность

### 1. Firewall

```bash
# Настройка UFW
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 2. SSL/TLS

```bash
# Автоматическое обновление сертификатов
crontab -e
# Добавить: 0 2 * * * certbot renew --quiet
```

### 3. Мониторинг безопасности

```bash
# Проверка уязвимостей
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image rag-system:latest
```

## Масштабирование

### Горизонтальное масштабирование

```bash
# Увеличение количества реплик API
docker-compose up -d --scale rag-api=5

# Использование load balancer
# Настройте nginx или HAProxy для распределения нагрузки
```

### Вертикальное масштабирование

```yaml
# Увеличение ресурсов в docker-compose.yml
services:
  rag-api:
    deploy:
      resources:
        limits:
          memory: 16G
          cpu: 4000m
```

## Обновления

### Rolling Updates

```bash
# Обновление с нулевым downtime
docker-compose up -d --no-deps rag-api
```

### Blue-Green Deployment

```bash
# Создание новой версии
docker-compose -f docker-compose.blue.yml up -d

# Переключение трафика
# Обновление nginx конфигурации

# Остановка старой версии
docker-compose -f docker-compose.green.yml down
```
