# FIT4110 Lab 05 — A5 Analytics Service

## Mục tiêu

Lab 05 điều phối ba container bằng Docker Compose:

```text
Core Business / Postman
          |
          | POST /events/core
          v
  A5 Analytics API :8000
       |                 |
       | PostgreSQL      | HTTP /analyze
       v                 v
 PostgreSQL :5432   Analytics Worker :9000
```

API nhận các event `policy.decision.created`, `alert.created`, `alert.resolved`, gọi worker để phân loại rủi ro, sau đó lưu kết quả vào PostgreSQL. Endpoint `/analytics/summary` trả thống kê theo loại event và nhóm rủi ro.

## Thành phần

- `api`: FastAPI, port `8000`, chạy bằng user non-root.
- `analytics-worker`: FastAPI mock analytics, port `9000`, chạy bằng user non-root.
- `db`: PostgreSQL 15, lưu dữ liệu bằng named volume.
- `team-internal`: mạng nội bộ của ba service.
- `class-net`: mạng để API có thể kết nối với service của nhóm khác.

## Chạy nhanh

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Kiểm tra:

```bash
curl http://localhost:8000/health
curl http://localhost:9000/health
```

Chạy kiểm thử end-to-end:

```bash
npm install
npm run test:compose
```

Report được tạo tại:

```text
reports/newman-lab05-compose.xml
reports/newman-lab05-compose.html
```

## API chính

| Method | Endpoint | Mô tả | Auth |
|---|---|---|---|
| GET | `/health` | Kiểm tra API, DB và worker | Không |
| POST | `/events/core` | Nhận event từ Core Business | Bearer token |
| GET | `/events/recent` | Lấy event mới nhất | Bearer token |
| GET | `/analytics/summary` | Thống kê tổng hợp | Bearer token |

Token local mặc định:

```text
Bearer local-dev-token
```

## Ví dụ gửi event

```bash
curl -X POST http://localhost:8000/events/core \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "b3cbe2aa-1281-42a8-b2ca-66cb91304bd8",
    "eventType": "policy.decision.created",
    "eventVersion": "1.0.0",
    "occurredAt": "2026-06-17T10:00:00+07:00",
    "correlationId": "corr-lab05-001",
    "source": "core-business",
    "data": {
      "decision": "DENIED",
      "policyId": "POL-001"
    }
  }'
```

## Artefact

- `docker-compose.yml`
- `Dockerfile` và `Dockerfile.worker`
- `contracts/analytics.openapi.yaml`
- `postman/collections/A5_Analytics_Lab05.postman_collection.json`
- `postman/environments/A5_Analytics_Lab05_Local.postman_environment.json`
- `checklists/readiness-checklist.md`
- `RUN_COMPOSE.md`
