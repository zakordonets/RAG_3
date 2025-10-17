@echo off
pushd "%~dp0\..\.."
echo Starting RAG System Monitoring Stack...
echo.

echo Starting Prometheus and Grafana...
docker-compose -f docker-compose.monitoring.yml up -d

echo.
echo ========================================
echo Monitoring Stack Started!
echo ========================================
echo.
echo Prometheus: http://localhost:9090
echo Grafana:    http://localhost:8080
echo.
echo Grafana Login:
echo Username: admin
echo Password: admin123
echo.
echo ========================================
echo.
echo To stop monitoring:
echo docker-compose -f docker-compose.monitoring.yml down
echo.
popd
pause
