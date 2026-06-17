# Readiness Checklist – A5 Analytics Lab 05

- [x] **Database ready:** PostgreSQL có `pg_isready`, volume riêng và API tự tạo bảng `analytics_events`.
- [x] **Analytics worker ready:** worker chạy non-root, có `/health` và `/analyze`.
- [x] **API ready:** API chạy non-root, `/health` kiểm tra cả DB và worker; `/events/core` lưu event thật.
- [x] **Environment variables:** cấu hình nằm trong `.env.example`; không commit token hoặc mật khẩu thật.
- [x] **Network & ports:** `team-internal` dùng cho API–DB–worker; API tham gia `class-net`; host map 8000 và 9000.
- [x] **Image tags:** image mặc định dùng tag `v0.5.0-team-analytics`; có thể override bằng `API_IMAGE` và `WORKER_IMAGE`.

## Kiểm tra trước khi nộp

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
curl http://localhost:9000/health
npm run test:compose
```

> Việc push image lên Docker Hub/GHCR cần thực hiện bằng tài khoản registry của nhóm trước khi nộp.
