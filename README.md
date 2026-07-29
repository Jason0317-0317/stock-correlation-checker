# 股票相關性檢查器

一款 Windows 桌面應用程式，用歷史「日報酬率」的 Pearson 相關係數，檢查多檔股票是否看似分散、實際上卻經常一起漲跌。

## 功能

- 原生 Windows 桌面介面，不使用 Streamlit 或瀏覽器
- 支援美股與 Yahoo Finance 可查詢的市場；台股代號例如 `2330.TW`
- 相關矩陣熱圖與標準化價格走勢
- 依相關係數排序所有股票配對
- 自訂高相關警戒值
- 背景下載資料，操作介面不會凍結
- 匯出分析結果 CSV

## 開發環境執行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## 建立 Windows 應用程式

在 PowerShell 執行：

```powershell
.\build.ps1
```

完成後，把整個 `dist\StockCorrelationChecker` 資料夾複製到其他 Windows 電腦。使用者雙擊 `StockCorrelationChecker.exe` 即可，不需要另外安裝 Python。

程式仍需連線至 Yahoo Finance 才能下載行情。

## 分析觀念

本工具計算的是日報酬率相關性，而不是股價相關性。直接比較股價，常會因長期趨勢而產生誤導。一般可把 `0.7` 以上視為高度同向，但門檻應配合投資策略、產業與觀察期間調整。

相關係數只描述歷史線性關係，可能隨市場環境快速改變；它不是投資建議，也不能單獨代表投資組合風險。
