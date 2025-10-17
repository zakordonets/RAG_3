Set-Location -Path (Join-Path $PSScriptRoot '..\\..')
Write-Host "Starting RAG System Monitoring Stack..." -ForegroundColor Green
Write-Host ""

Write-Host "Starting Prometheus and Grafana..." -ForegroundColor Yellow
docker-compose -f docker-compose.monitoring.yml up -d

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Monitoring Stack Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host "Grafana:    http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "Grafana Login:" -ForegroundColor Yellow
Write-Host "Username: admin" -ForegroundColor White
Write-Host "Password: admin123" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop monitoring:" -ForegroundColor Yellow
Write-Host "docker-compose -f docker-compose.monitoring.yml down" -ForegroundColor White
Write-Host ""

Read-Host "Press Enter to continue"
