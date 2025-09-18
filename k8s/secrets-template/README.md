# 🔐 Kubernetes Secrets Templates

Эта папка содержит шаблоны для создания Kubernetes секретов. Реальные секреты исключены из репозитория по соображениям безопасности.

## 📋 Необходимые секреты

### 1. Application Secrets (`secret.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-secrets
  namespace: rag-system
type: Opaque
data:
  # Base64 encoded values
  YANDEX_API_KEY: <base64-encoded-key>
  DEEPSEEK_API_KEY: <base64-encoded-key>
  GPT5_API_KEY: <base64-encoded-key>
  TELEGRAM_BOT_TOKEN: <base64-encoded-token>
  QDRANT_API_KEY: <base64-encoded-key>
```

### 2. Registry Secrets (`registry-secret.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: registry-secret
  namespace: rag-system
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

### 3. TLS Secrets (`tls-secret.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tls-secret
  namespace: rag-system
type: kubernetes.io/tls
data:
  tls.crt: <base64-encoded-certificate>
  tls.key: <base64-encoded-private-key>
```

## 🛠️ Создание секретов

### Из командной строки

```bash
# Application secrets
kubectl create secret generic rag-secrets \
  --from-literal=YANDEX_API_KEY=your_yandex_key \
  --from-literal=DEEPSEEK_API_KEY=your_deepseek_key \
  --from-literal=GPT5_API_KEY=your_gpt5_key \
  --from-literal=TELEGRAM_BOT_TOKEN=your_bot_token \
  --from-literal=QDRANT_API_KEY=your_qdrant_key \
  --namespace=rag-system

# Docker registry secret
kubectl create secret docker-registry registry-secret \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --docker-email=your-email@example.com \
  --namespace=rag-system

# TLS secret
kubectl create secret tls tls-secret \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  --namespace=rag-system
```

### Из файлов

```bash
# Создать секреты из YAML файлов (после заполнения шаблонов)
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/registry-secret.yaml
kubectl apply -f k8s/tls-secret.yaml
```

## 🔒 Кодирование Base64

```bash
# Кодирование строки в Base64
echo -n "your-secret-value" | base64

# Декодирование из Base64
echo "eW91ci1zZWNyZXQtdmFsdWU=" | base64 -d
```

## 📝 Шаблоны для копирования

### secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-secrets
  namespace: rag-system
type: Opaque
data:
  YANDEX_API_KEY: ""          # echo -n "your_key" | base64
  DEEPSEEK_API_KEY: ""        # echo -n "your_key" | base64
  GPT5_API_KEY: ""            # echo -n "your_key" | base64
  TELEGRAM_BOT_TOKEN: ""      # echo -n "your_token" | base64
  QDRANT_API_KEY: ""          # echo -n "your_key" | base64
```

### registry-secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: registry-secret
  namespace: rag-system
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: ""       # Base64 encoded Docker config JSON
```

### tls-secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tls-secret
  namespace: rag-system
type: kubernetes.io/tls
data:
  tls.crt: ""                 # Base64 encoded certificate
  tls.key: ""                 # Base64 encoded private key
```

## ⚠️ Важные замечания

1. **Никогда не коммитьте реальные секреты** в git репозиторий
2. **Используйте внешние системы управления секретами** (Vault, AWS Secrets Manager, etc.) в production
3. **Ограничьте доступ** к секретам через RBAC
4. **Регулярно ротируйте** API ключи и токены
5. **Мониторьте доступ** к секретам через аудит логи

## 🔄 Обновление секретов

```bash
# Обновить существующий секрет
kubectl patch secret rag-secrets -n rag-system \
  --type='json' \
  -p='[{"op": "replace", "path": "/data/YANDEX_API_KEY", "value": "bmV3LWtleQ=="}]'

# Или пересоздать
kubectl delete secret rag-secrets -n rag-system
kubectl create secret generic rag-secrets --from-literal=YANDEX_API_KEY=new-key --namespace=rag-system
```

---

*Всегда храните секреты в безопасности и следуйте принципам наименьших привилегий.*
