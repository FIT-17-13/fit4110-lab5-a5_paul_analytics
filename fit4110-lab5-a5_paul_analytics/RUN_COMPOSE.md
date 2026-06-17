# Hướng dẫn chạy A5 Analytics Lab 05

## 1. Chuẩn bị

Yêu cầu Docker Desktop có Docker Compose v2. Node.js chỉ cần khi chạy Newman.

```bash
git clone <repo-url>
cd fit4110-lab5-a5_paul_analytics
cp .env.example .env
```

## 2. Build và chạy stack

```bash
docker compose up -d --build
```

Theo dõi trạng thái:

```bash
docker compose ps
docker compose logs -f
```

Kết quả mong đợi: `db`, `analytics-worker` và `api` đều ở trạng thái `healthy`.

## 3. Kiểm tra readiness

```bash
curl http://localhost:9000/health
curl http://localhost:8000/health
docker exec fit4110-a5-analytics-db pg_isready -U lab05 -d analyticsdb
```

API health hợp lệ:

```json
{
  "status": "ok",
  "service": "a5-analytics-api",
  "version": "0.5.0-team-analytics",
  "database": "ok",
  "worker": "ok"
}
```

## 4. Chạy Newman

```bash
npm install
npm run test:compose
```

Collection kiểm tra health, xác thực token, tạo event, lấy recent events và analytics summary.

## 5. Gỡ lỗi

```bash
docker compose logs api
docker compose logs analytics-worker
docker compose logs db
```

Reset sạch database:

```bash
docker compose down -v
docker compose up -d --build
```

Nếu port bị chiếm, sửa `APP_PORT` hoặc `WORKER_PORT` trong `.env`.

## 6. Dừng stack

```bash
docker compose down
```

## 7. Tag và push image

Thay `<dockerhub-user>` bằng tài khoản của nhóm:

```bash
docker tag a5-analytics-api:v0.5.0-team-analytics <dockerhub-user>/a5-analytics-api:v0.5.0-team-analytics
docker tag a5-analytics-worker:v0.5.0-team-analytics <dockerhub-user>/a5-analytics-worker:v0.5.0-team-analytics
docker push <dockerhub-user>/a5-analytics-api:v0.5.0-team-analytics
docker push <dockerhub-user>/a5-analytics-worker:v0.5.0-team-analytics
```
