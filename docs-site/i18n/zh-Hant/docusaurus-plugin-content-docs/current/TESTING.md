# 測試策略

## 自動化層級

1. Unit tests：時間解析、來源 normalization、驗證、時間 folds、metrics 與特徵可用性。
2. Contract tests：代表性台北、新北與天氣 payloads。
3. Pipeline tests：raw fixture 到 normalized Parquet 再到 labelled features。
4. API tests：health、查詢驗證、上游失敗映射與 model-not-ready 行為。
5. Frontend checks：TypeScript build、loading、failure、filtering、selection、桌面與行動版型。
6. Deployment smoke tests：公開 health URL、站點數、新鮮度、CORS 與模型版本。

合成 end-to-end test 會訓練所有候選模型、套用時序門檻、寫入勝出 model/evaluation/driver artifacts、提供有界預測並執行天氣 what-if。合成資料只驗證管線，絕不當成真實模型表現。

## 必要指令

```bash
pytest
ruff check src tests
cd frontend && npm run build
cd infra/cloudflare-collector && npm run typecheck
cd docs-site && npm run typecheck && npm run build
```

Release checks 另執行 `npm run lint`、`npm audit`、`git diff --check` 與 Docker backend build。

## ML 專屬測試

- 任何 training timestamp 不得晚於該 fold train cutoff。
- Validation 必須在 60 分鐘 purge gap 之後開始。
- 最後 24 小時不得出現於模型選擇。
- Target 必須配對同站且落在 53–67 分鐘區間。
- Weather issue time 不得晚於 observation time。
- 預測必須為有限數，clip 後位於站點範圍。
- 儲存特徵順序必須與 inference 相同。
