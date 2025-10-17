@echo off
pushd "%~dp0\..\.."
echo Starting Redis with Docker Compose...
docker-compose up -d redis
echo.
echo Redis is starting up...
echo You can check status with: docker-compose ps
echo You can view logs with: docker-compose logs redis
echo.
echo Redis will be available at: redis://localhost:6379
popd
pause
