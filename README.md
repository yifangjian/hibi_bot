# hibi_bot

高級日語課堂外自主練習用 LINE Chatbot，結合產出導向法（Production-Oriented Approach, POA）與生成式 AI 即時解釋型回饋，同時作為準實驗研究的資料蒐集系統。

> 目前進度：Phase 1（專案骨架）、Phase 2（圖文選單串接）、Phase 3（Flex Message 題目卡片與回饋卡片）皆已完成並上線測試過。三種模式的「開始練習 → 作答 → 回饋 → 再練一題」完整流程已可運作；回饋卡片的解釋文字目前為 `explanation_rule` 欄位的 placeholder 顯示，尚未串接 OpenAI；AI 助教與推播排程尚為 stub，留待後續階段。

## 1. 專案簡介

大學高級日語課程的學習者，往往在課堂之外缺乏持續練習的動機與管道；即使有練習教材，傳統的批改回饋也多半止於「對／錯」，難以針對高級日語學習者需要的細膩語感（詞彙搭配、語境選用、諺語的比喻邏輯等）給出即時且個別化的說明。

hibi_bot 希望透過學生每天都在使用的 LINE，把練習變成一件低門檻、隨手可做的事：學生點開圖文選單、選一題、送出答案，幾秒內就能收到針對這一題「為什麼對／為什麼錯」的解釋，而不只是一個分數。同時，這個系統也是研究者用來蒐集「解釋型 AI 回饋是否能提升高級日語學習成效」的準實驗平台。

## 2. 系統架構

**技術棧**

| 用途 | 技術 |
| --- | --- |
| 後端框架 | FastAPI（Python） |
| LINE 介面 | LINE Messaging API（line-bot-sdk v3） |
| 資料庫 | Supabase（PostgreSQL） |
| AI 回饋生成 | OpenAI API（預設 `gpt-5.4-mini`，依前導試行結果可調整） |
| 部署 | Railway |
| 推播排程 | Railway Cron Job 定時呼叫內部端點（不使用常駐 APScheduler，避免部署重啟導致排程遺失） |

**架構圖**：（待補）

## 3. 核心設計理念

系統的互動流程對應 POA 的「驅動－促成－評價」三階段：

| POA 階段 | 教學意涵 | 系統設計對應 |
| --- | --- | --- |
| 驅動（Motivating） | 引發學習者對特定語言表達的需求與好奇 | 圖文選單主動推送情境化題目，降低「不知道要練什麼」的啟動門檻 |
| 促成（Enabling） | 提供學習者完成任務所需的語言鷹架 | 每題附帶人工標註的 `explanation_rule`，作為 AI 生成回饋的依據，避免自由發揮偏離教學重點 |
| 評價（Assessing） | 檢視學習成果並提供回饋以促進內化 | 作答後即時生成解釋型回饋；答錯的題目進入錯題狀態追蹤，直到學習者主動解決 |

## 4. 功能特色

- **三種練習模式**
  - 単語：單階段，情境例句挖空＋選項（選正確讀音）
  - 諺：兩階段設計（語意／情境選擇題 → 讀音輸入題，兩階段合併判定為一筆作答紀錄）
  - 言語知識：單階段，情境例句挖空＋選項，與諺的情境式選擇題共用同一套 Flex 模板
- **圖文選單設計**：四層選單（主選單／模式選單／開始練習子選單／錯題模式子選單），透過 LINE 原生 `richmenuswitch` 切換並同步回傳 postback 供後端記錄行為
- **解釋型回饋機制**：作答後顯示對應該題 `explanation_rule` 的說明（目前為 placeholder 顯示，Phase 4 起改由 OpenAI API 即時生成個別化解釋）

## 5. 研究背景

本專案是一項準實驗研究的資料蒐集系統的一部分，探討生成式 AI 即時解釋型回饋對高級日語學習者課後自主練習成效的影響。（研究計畫連結：待補）

## 6. 本機開發設置

**環境需求**：Python 3.11+

```bash
# 建立虛擬環境並安裝依賴
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env，填入 LINE_CHANNEL_SECRET、LINE_CHANNEL_ACCESS_TOKEN、
# SUPABASE_URL、SUPABASE_KEY、OPENAI_API_KEY

# 啟動本機伺服器
uvicorn app.main:app --reload
```

**資料庫設置**：於 Supabase 專案的 SQL Editor 中執行 [`app/db/schema.sql`](app/db/schema.sql)。

**本機測試 LINE webhook**：由於 LINE 平台需要對外可存取的 HTTPS 端點，本機開發可使用 [ngrok](https://ngrok.com/) 建立臨時通道（`ngrok http 8000`），再將產生的網址填入 LINE Developers Console 的 Webhook URL；也可以使用 LINE 官方提供的 Webhook 驗證工具（Console 內的「Verify」按鈕）確認端點是否正常回應。

**圖文選單設置**：`.env` 填好 `LINE_CHANNEL_ACCESS_TOKEN` 後，執行一次：

```bash
python scripts/setup_richmenu.py
```

會建立所有 rich menu、上傳圖片、建立 alias、設定預設選單，並輸出 `richmenu_ids.json`（僅供除錯，已加入 `.gitignore`）。

**測試練習流程**：資料庫執行過 `schema.sql` 後，先灌入測試題庫：

```bash
python scripts/seed_sample_questions.py
```

會建立単語 x2、言語知識 x2、諺 x1 對（語意/情境選擇 + 讀音輸入）的最小題庫。接著用測試帳號加官方帳號好友，實際跑一次：

1. 點選單「単語」→「開始練習」→ 回答題目卡片上的選項 → 確認收到回饋卡片 →「再練一題」
2. 點選單「諺」→「開始練習」→ 回答第一階段選項 → 收到讀音輸入提示卡 → 直接在聊天室輸入平假名 → 確認收到合併判定後的回饋卡片
3. 點「開始練習」子選單裡的「AI助教」→ 收到輸入題號的提示 → 輸入任意數字 → 確認收到 placeholder 回覆

跑完後可到 Supabase 後台檢查：
- `attempts_log`：每完成一題（諺為兩階段合併後）應新增一筆，`is_correct` 與作答內容正確；諺的紀錄 `answer_detail` 應包含兩階段細節
- `wrong_question_state`：答錯的題目狀態為 `wrong`，答對且原本錯誤的題目應變為 `resolved`
- `unit_progress`：該單元全部題目都作答過後 `all_attempted` 應為 `true`；錯題全部清除後 `all_wrong_resolved` 應為 `true`

## License

本專案採用 [MIT License](LICENSE)。
