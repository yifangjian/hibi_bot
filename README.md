# hibi_bot

高級日語課堂外自主練習用 LINE Chatbot，結合產出導向法（Production-Oriented Approach, POA）與生成式 AI 即時解釋型回饋，同時作為準實驗研究的資料蒐集系統。

> 目前進度：Phase 1～6 皆已完成並上線測試過。回饋卡片已改由 OpenAI 依 `explanation_rule` 即時生成個別化解釋；AI 助教可依題號查詢並解析特定題目，追問對話有每日輪次限制；系統每天固定時間主動推播「每日挑戰」，使用者完成後會收到動態生成的圖卡；重置、進度查詢、錯題複習等核心練習迴圈也已完整串接。至此 hibi_bot 的核心功能已完整，後續重點轉為正式題庫整理與前導試行。

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
| 完成圖卡生成 | Pillow（動態產生圖片）＋ Supabase Storage（public bucket 存放並取得公開網址） |
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
- **解釋型回饋機制**：作答後由 OpenAI API 根據該題的 `explanation_rule` 即時生成個別化解釋（system prompt 明確限制 AI 只能依據 `explanation_rule` 說明，不得引入題庫外的文法知識），生成結果存入 `feedback_logs`
- **AI 助教**：使用者輸入題號後可取得該題的解析（Flex 卡片呈現，system prompt 明確禁止 markdown 語法避免在 LINE 顯示異常）；解析後進入追問模式，可直接在聊天室打字繼續問，對話歷程存入 `ai_conversation_log`，每日追問輪次有上限（預設 10 輪，逾限不呼叫 OpenAI，回覆卡片會顯示剩餘次數）；卡片下方提供「問其他題」「繼續練習」兩個按鈕方便銜接下一步
- **每日挑戰**：Railway Cron 每天固定時間（台灣時間中午 12:00）為每位使用者隨機產生一份橫跨三模式、最多 5 題的挑戰並推播；每題作答同步寫入對應模式的既有進度系統（`attempts_log`／`wrong_question_state`／`scope_progress`，與自主練習共用同一套邏輯），完成後生成含使用者名稱、答對率、日期的圖卡（Pillow 動態產生、存於 Supabase Storage），選單自動切回主選單；中途離開可從聊天室的舊卡片接續作答，跨天則視為過期
- **錯題模式**：從 `wrong_question_state` 挑一題該模式底下狀態仍是 `wrong` 的題目複習，答對後自動標記為 `resolved` 並可連續複習下一題（`attempt_type` 記為 `review`，與一般練習的 `first` 區分）；沒有待複習的錯題時會明確告知
- **重置**：需該範圍當下輪次「全部作答完」且「沒有任何待複習錯題」才允許，只把 `scope_progress` 的追蹤狀態打回起點（`current_round` +1），不觸碰 `attempts_log`／`wrong_question_state` 等歷史紀錄，過去每一輪的資料完整保留可供研究分析
- **進度查詢**：一張卡片同時顯示三模式各自的範圍、輪次、本輪作答進度、待複習錯題數，以及每日挑戰「累計完成次數」（刻意不做「連續天數」，避免使用者因為某天沒使用而產生「破功」的挫折感，呼應本研究降低能力感焦慮的目標）

## 5. 研究背景

本專案是一項準實驗研究的資料蒐集系統的一部分，探討生成式 AI 即時解釋型回饋對高級日語學習者課後自主練習成效的影響。（研究計畫連結：待補）

## 6. 本機開發設置

**環境需求**：Python 3.11+、[Git LFS](https://git-lfs.com/)（完成圖卡用的中文字型檔案 `assets/fonts/NotoSansTC-Bold.otf` 透過 LFS 存放；clone 前請先安裝並執行 `git lfs install`，否則該檔案只會是一段指標文字而非真正的字型檔）

```bash
# 建立虛擬環境並安裝依賴
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env，填入 LINE_CHANNEL_SECRET、LINE_CHANNEL_ACCESS_TOKEN、
# SUPABASE_URL、SUPABASE_KEY、OPENAI_API_KEY
# OPENAI_MODEL 預設 gpt-5.4-mini，AI_TUTOR_DAILY_TURN_LIMIT 預設 10（AI 助教每日追問輪次上限），
# 兩者皆可依實際情況調整，不需修改程式碼

# 啟動本機伺服器
uvicorn app.main:app --reload
```

**資料庫設置**：於 Supabase 專案的 SQL Editor 中執行 [`app/db/schema.sql`](app/db/schema.sql)。

**考試範圍（`exam_scope`）設定**：題目不再用「單元 1、單元 2」這種假設有順序的編號分類，而是用一個文字標籤（例如「期中考」「小考3」）分組，因為實際考試範圍常常不是照單元順序切、有時甚至完全不按單元劃分。系統同一時間每個模式只會有「一個目前教學進度對應的範圍」，記錄在 `active_exam_scope` 表（`mode` 為主鍵）。目前沒有管理後台，換範圍（例如换到下一次段考的內容）直接在 Supabase SQL Editor 執行：

```sql
UPDATE active_exam_scope SET exam_scope = '期末考', updated_at = now() WHERE mode = 'vocab';
```

只要新範圍的題目用新的 `exam_scope` 值匯入 `questions` 表，`current_round` 就會自動從第 1 輪開始（沒有 `scope_progress` 紀錄時的預設值），不需要額外處理；舊範圍的所有作答歷史完整保留在 `attempts_log`，不受影響。

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

1. 點選單「単語」→「開始練習」→ 回答題目卡片上的選項 → 確認收到的回饋卡片是 OpenAI 生成的個別化解釋（不是 `explanation_rule` 原文）→「再練一題」
2. 點選單「諺」→「開始練習」→ 回答第一階段選項 → 收到讀音輸入提示卡 → 直接在聊天室輸入平假名 → 確認收到合併判定後的回饋卡片
3. 點「開始練習」子選單裡的「AI助教」→ 輸入有效題號（例如 `1`）→ 確認收到該題的 AI 解析卡片 → 直接在聊天室打字繼續追問 → 確認可以連續對話，且卡片下方能看到剩餘額度、以及「問其他題」「繼續練習」按鈕
4. 若要測試每日輪次上限：可先把 `.env` 的 `AI_TUTOR_DAILY_TURN_LIMIT` 暫時調低（例如 `2`）方便快速測試，追問超過上限後應收到「今日 AI 助教對話次數已達上限」，且不會再呼叫 OpenAI（測完記得改回原本的值）

跑完後可到 Supabase 後台檢查：
- `attempts_log`：每完成一題（諺為兩階段合併後）應新增一筆，`is_correct` 與作答內容正確；諺的紀錄 `answer_detail` 應包含兩階段細節
- `wrong_question_state`：答錯的題目狀態為 `wrong`，答對且原本錯誤的題目應變為 `resolved`
- `scope_progress`：該範圍全部題目都作答過後 `all_attempted` 應為 `true`；錯題全部清除後 `all_wrong_resolved` 應為 `true`
- `feedback_logs`：每次作答應新增一筆，`ai_generated_text` 有內容、`model_used` 為目前設定的模型名稱
- `ai_conversation_log`：AI 助教的每一輪輸入/回覆都應各存一筆（`role='user'`／`role='assistant'`）
- `ai_conversation_usage`：追問輪次應累加 `turn_count`（初次解析不計入）

**測試錯題複習、重置、進度查詢**：

1. 故意答錯一題（例如選非正確答案的選項），確認 `wrong_question_state` 出現一筆 `status='wrong'`
2. 點模式選單的「錯題模式」→「複習錯題」→ 回答同一題選對 → 確認 `wrong_question_state` 該筆變成 `resolved`、`attempts_log` 新增一筆 `attempt_type='review'`；若還有其他錯題，「繼續複習」按鈕會接著出下一題，直到沒有錯題為止
3. 把該範圍剩下的題目都答完（`scope_progress.all_attempted` 應變 `true`）且沒有未解決的錯題後，點「重置」→ 確認收到「已重置！你現在進入第 N 輪」，`scope_progress.current_round` +1、`all_attempted`／`all_wrong_resolved` 打回 `false`，同時 `attempts_log` 裡舊輪次的紀錄完全沒被更動
4. 若題目/錯題都還沒完成就先點「重置」，應該收到對應的擋下訊息（「還有題目尚未作答完」或「你還有 N 題錯題尚未複習完成」），且不會有任何資料庫寫入
5. 點主選單「我的進度」或模式選單「進度」，確認卡片顯示的三模式範圍/輪次/本輪進度/待複習錯題數，都與 Supabase 後台的即時資料一致；每日挑戰「累計完成次數」則對應 `daily_challenge` 裡 `completed=true` 的總筆數

**Supabase Storage 設置（每日挑戰完成圖卡用）**：需要一個 public bucket 存放動態產生的完成圖卡。在 Supabase 後台的 Storage 頁面手動建立，或用 Python 直接建立：

```python
from supabase import create_client
from storage3.types import CreateOrUpdateBucketOptions

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase.storage.create_bucket(
    id="completion-cards",
    name="completion-cards",
    options=CreateOrUpdateBucketOptions(public=True, file_size_limit=5 * 1024 * 1024, allowed_mime_types=["image/png"]),
)
```

bucket 名稱固定為 `completion-cards`（寫死在 `app/services/completion_card_generator.py`），必須設為 public 才能讓 LINE 的 Image Message 讀取到圖片網址。完成圖卡使用的中文字型（`assets/fonts/NotoSansTC-Bold.otf`）已隨 repo 附上，不需要額外安裝系統字型（Railway 的 Linux 容器不會有 macOS 系統字型，所以特別包進 repo 裡確保部署後仍能正確顯示中文）。

**Railway Cron 設置（每日推播）**：

1. `.env` 設定 `INTERNAL_CRON_SECRET`（自訂一組隨機字串，例如 `openssl rand -hex 32`），Railway 服務的環境變數也要設定同樣的值
2. 在 Railway 專案裡新增一個 Cron Job，排程設定為每天 UTC 04:00（對應台灣時間 UTC+8 中午 12:00）：
   ```
   0 4 * * *
   ```
3. Cron Job 執行的指令是對內部端點發送 POST 請求，帶上密鑰標頭：
   ```bash
   curl -X POST https://<your-railway-app>.up.railway.app/internal/push-daily \
     -H "X-Cron-Secret: $INTERNAL_CRON_SECRET"
   ```
4. 本機測試不用等到中午，可以直接手動觸發（伺服器跑在本機、`.env` 已設定 `INTERNAL_CRON_SECRET` 的前提下）：
   ```bash
   curl -X POST http://localhost:8000/internal/push-daily \
     -H "X-Cron-Secret: <你在 .env 設定的值>"
   ```
   回應會是 `{"users": N, "pushed": M}`，`pushed` 是實際成功推播的人數（若某位使用者三個模式當下輪次都沒有剩餘題目，會被排除在外，不視為錯誤）。

跑完後可到 Supabase 後台檢查：
- `daily_challenge`：應新增一筆，`questions` 是決定好的題目順序（最多 5 題，橫跨三模式且不重複），`current_index`／`results`／`completed` 隨作答進度更新
- `push_log`：應新增一筆，`challenge_id` 對應剛才產生的挑戰
- 完成挑戰後，`attempts_log` 裡對應的幾筆應該都有 `daily_challenge_id`（指向這次挑戰）且 `pushed_at` 有值（等於 `push_log.pushed_at`）；相對地，透過「開始練習」自主作答的紀錄 `daily_challenge_id`／`pushed_at` 應維持 `NULL`

## License

本專案採用 [MIT License](LICENSE)。
