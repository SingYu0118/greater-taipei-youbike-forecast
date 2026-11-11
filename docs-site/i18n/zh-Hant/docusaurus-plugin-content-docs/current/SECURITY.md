# 安全與營運

## Secret 處理

- 本地憑證只由已排除 Git 的 `.env` 讀取。
- `.env.example` 只含名稱與安全預設值。
- Production secrets 必須使用托管平台的加密 secret store。
- R2 access keys 僅在 server side，絕不進 frontend build。

## 應用邊界

- Public API 除 what-if 外均唯讀；what-if 只在記憶體推論，不寫狀態。
- Worker 手動收集 route 需 bearer token secret；未設時停用。Cron 不需公開 trigger。
- CORS 來自 `ALLOWED_ORIGINS`；production 必須使用明確 HTTPS origins。
- 上游 API 失敗只回傳一般化訊息，不洩漏 response body。
- 情境數值輸入有界驗證。
- Container 以非特權使用者執行並提供 health check。

## 供應鏈檢查

GitHub Actions 安裝鎖定的 frontend、Worker 與 docs 依賴，每次 push 執行 Python static checks/tests、TypeScript compile 與 production builds。本地 release checks 額外對所有 Node projects 執行 `npm audit`，Docker 可用時建置 backend image。

## 公開部署前

1. 將 `ALLOWED_ORIGINS` 限制為最終前端網域。
2. 啟用任何可計費雲服務前設定 budget alerts。
3. 啟用 provider logs 與 failure notifications，但不記錄 credentials。
4. 驗證 model artifact checksum 與 training metadata。
5. 執行 public health、CORS、freshness、API contract 與 mobile smoke tests。
6. 確認 validated model artifacts 不存在時 API 仍回傳 HTTP 503。

## 事故 rollback

Frontend、backend、collector 與 model artifacts 獨立版本化。回滾至最後一個驗證過的不可變 revision；rollback 永遠不刪 raw history。
