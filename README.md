# hibi_bot

高級日語課堂外自主練習用 LINE Chatbot，結合產出導向法（Production-Oriented Approach, POA）與生成式 AI 即時解釋型回饋，同時作為準實驗研究的資料蒐集系統。

> 目前進度：Phase 1～6 皆已完成並上線測試過，核心功能完整。三種模式的正式題庫（高日暑修班期中考：諺語 100 句、単語 270 個讀音題、言語知識 661 題）皆已匯入完成，系統已部署上線（Railway，`--workers 2`）並串接正式 LINE 官方帳號。諺語練習改為同一句諺語隨機出「語意選択」或「文脈穴埋め」其中一種第一階段題目（見下方「諺語隨機變體設計」），単語題庫是詞彙讀音測驗形式、沒有解析內容，答題後直接顯示正確讀音、不呼叫 AI（見下方「単語題庫匯入」）。後續重點轉為前導試行。

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
  - 単語：單階段，詞彙讀音測驗（題目為單一詞彙，選項為可能的讀音）——原始設計是「情境例句挖空＋選項」，但目前匯入的實際題庫是純讀音測驗形式，見下方「単語題庫匯入」。`correct_option` 絕大多數是單一 option id，但少數詞彙有兩種都算正確的讀音（例如「異国情緒」的 じょうちょ／じょうしょ），這種情況資料用「、」分隔多個 id（例如 `"a、c"`），判分與回饋文字（`app/services/question_picker.py` 的 `is_correct_option()`、`app/services/feedback_generator.py` 的 `finish_feedback_text()`）都要用這個分隔慣例判斷，不能假設永遠是單一 id——這個假設曾經被違反過一次，造成某道題目不管選哪個選項都被判定答錯，且回饋文字直接把原始 id 字串（`"a、c"`）印出來而非讀音，詳見下一段
  - 諺：兩階段設計（語意／情境選擇題 → 讀音輸入題，兩階段合併判定為一筆作答紀錄）。情境選擇題（situational_choice）的例句常會把諺語做動詞變化以符合句意，但第二階段永遠是要求諺語「完整原型」的讀音，容易讓人誤解成要打例句裡變化後的形式，所以讀音輸入提示卡片（`build_reading_input_prompt_card`）明確提醒這一點
  - 言語知識：單階段，情境例句挖空＋選項，與諺的情境式選擇題共用同一套 Flex 模板
- **圖文選單設計**：四層選單（主選單／模式選單／開始練習子選單／錯題模式子選單），透過 LINE 原生 `richmenuswitch` 切換並同步回傳 postback 供後端記錄行為
- **解釋型回饋機制**：作答後由 OpenAI API 根據該題的 `explanation_rule` 即時生成個別化解釋（system prompt 明確限制 AI 只能依據 `explanation_rule` 說明，不得引入題庫外的文法知識；也明確要求說明句子本身要翻譯成繁體中文，不能把解釋依據裡的日文原句直接照抄進回覆），生成結果存入 `feedback_logs`。**単語模式例外**：単語題庫目前是純讀音測驗、沒有解析內容可以當依據，答對答錯本身也沒有需要 AI 說明的細膩語感，所以答題後直接顯示正確讀音，不呼叫 OpenAI、不寫入 `feedback_logs`（見 `app/services/menu_actions.py` 的 `_build_feedback_text`）
- **AI 助教**：使用者輸入題號後可取得該題的解析（Flex 卡片呈現，system prompt 明確禁止 markdown 語法避免在 LINE 顯示異常）；解析後進入追問模式，可直接在聊天室打字繼續問，對話歷程存入 `ai_conversation_log`，每日追問輪次有上限（預設 10 輪，逾限不呼叫 OpenAI，回覆卡片會顯示剩餘次數）；卡片下方提供「問其他題」「繼續練習」兩個按鈕方便銜接下一步
- **每日挑戰**：Railway Cron 每天固定時間（台灣時間中午 12:00）為每位使用者隨機產生一份橫跨三模式、最多 5 題的挑戰並推播；每題作答同步寫入對應模式的既有進度系統（`attempts_log`／`wrong_question_state`／`scope_progress`，與自主練習共用同一套邏輯），每答完一題都會顯示解析回饋卡片（跟自主練習共用同一套 AI 生成邏輯，単語模式一樣是直接顯示正確讀音、不呼叫 AI），使用者按「下一題」才會真正推進到下一題／觸發完成流程——挑戰進度本身在顯示回饋卡片前就先寫入，不等使用者按下一題，避免看完解析後中途離開導致這一題沒被記錄到；完成後生成含使用者名稱、答對率、日期的圖卡（Pillow 動態產生、存於 Supabase Storage），選單自動切回主選單；中途離開可從聊天室的舊卡片接續作答，跨天則視為過期
- **錯題模式**：從 `wrong_question_state` 挑一題該模式底下狀態仍是 `wrong` 的題目複習，答對後自動標記為 `resolved` 並可連續複習下一題（`attempt_type` 記為 `review`，與一般練習的 `first` 區分）；沒有待複習的錯題時會明確告知
- **重置**：需該範圍當下輪次「全部作答完」且「沒有任何待複習錯題」才允許，只把 `scope_progress` 的追蹤狀態打回起點（`current_round` +1），不觸碰 `attempts_log`／`wrong_question_state` 等歷史紀錄，過去每一輪的資料完整保留可供研究分析
- **進度查詢**：一張卡片同時顯示三模式各自的範圍、輪次、本輪作答進度、待複習錯題數，以及每日挑戰「累計完成次數」（刻意不做「連續天數」，避免使用者因為某天沒使用而產生「破功」的挫折感，呼應本研究降低能力感焦慮的目標）
- **輸入中動畫**：呼叫 AI 生成解析／回覆前（`app/services/line_client.py` 的 `show_loading_animation()`），先呼叫 LINE 的 Loading Animation API 讓使用者看到「輸入中」提示，只套用在真的會等比較久的互動（`answer`／`review_answer`／`daily_challenge_answer` 這三個 postback action，以及文字訊息裡 `awaiting_reading_input`／`awaiting_ai_tutor_question_number`／`in_ai_tutor_conversation` 這三種等待狀態），不套用在「下一題」「查進度」這類幾乎瞬間回覆的動作（動畫一閃即逝、沒有意義）。動畫會在我們真正送出回覆的當下自動消失，`loading_seconds` 故意設最大值 60 秒當保險，不會有「動畫消失了但答案還沒出現」的狀況；呼叫本身包在 try/except 裡，這只是體驗加分，失敗不該影響真正的回覆流程。
- **使用者停用機制**：`users` 表的 `is_active`（預設 `true`）用來標記「確認不是研究參與者」的帳號（例如事後跟問卷填答名單核對後發現不在名單內）。停用只是把這個欄位改成 `false`，**不會刪除該使用者任何歷史資料**（`attempts_log`／`wrong_question_state`／`feedback_logs` 等全部保留，供之後資料清洗判斷排除範圍用）。`app/routers/webhook.py` 在 `get_or_create_user()` 之後立刻檢查這個欄位，被停用的使用者不管傳文字或按選單，一律只收到固定的停用說明文字，不會進入任何練習/選單邏輯，也不會再新增 `menu_interaction_log`；`daily_challenge.run_daily_push()` 的查詢也排除 `is_active=false`，停用的使用者不會再收到每日挑戰推播。之後如果還有類似「確認非參與者」的情況，只要把對應使用者的 `is_active` 設成 `false` 即可，不需要再改程式碼。

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

`question_number`（人類可讀題號，供 AI 助教輸入題號查詢用）只在同一個 `(mode, exam_scope)` 內唯一，不是全域唯一——因為每次考期換 `exam_scope` 都會重新從 1 編號，如果做成全域唯一，下一次考期匯入新題庫時題號一定會撞到上一次考期的題號。AI 助教查詢時會先看該模式目前的 `active_exam_scope` 再查題號，因此換範圍後，同一個數字自然對應到新範圍裡的題目，不會查到舊範圍的題目。

### 諺語隨機變體設計

諺語題目匯入時，同一句諺語會寫入 3 筆 `questions` 資料，共用同一個 `question_number`，用 `stage` 欄位區分：

- `semantic_choice`：意味選択（「這個諺語的意思是？」）
- `situational_choice`：文脈穴埋め（「符合這個情境的諺語是？」）
- `reading_input`：読み方（讀音輸入，第二階段固定使用）

使用者每次練習到某句諺語時，系統會在 `semantic_choice`／`situational_choice` 兩者之間**隨機擇一**當作第一階段題目（見 [`app/services/question_picker.py`](app/services/question_picker.py) 的 `get_scope_candidates`／`_pick_representative`），第二階段一律接同一個 `question_number` 底下的 `reading_input`。判斷「這句諺語本輪是否已作答過」時是以 `question_number` 為準，不是以個別變體的資料列 id 為準，所以同一句諺語不會因為兩種變體對系統來說是「不同題目」而被重複選中。這次隨機選到的是哪個變體會記錄在 `attempts_log.answer_detail.stage1_variant`，供後續分析兩種出題形式的正確率是否有差異。

### 諺語題庫匯入（`scripts/import_proverb_questions.py`）

用途：讀取 `data/raw/` 底下的 Excel 檔案（意味選択／文脈穴埋め／読み方三個工作表，依列順序一一對應同一句諺語），寫入 `questions` 表。

```bash
# 先跑小批次（前 5 句）確認流程沒問題
python scripts/import_proverb_questions.py \
    --file "data/raw/檔名.xlsx" --exam-scope "範圍名稱" --limit 5

# 確認沒問題後，正式全量匯入
python scripts/import_proverb_questions.py \
    --file "data/raw/檔名.xlsx" --exam-scope "範圍名稱"
```

**重複使用注意事項（重要，避免誤用造成重複資料）**：

- 這是「全量匯入」腳本，不是增量／upsert。執行前會先檢查指定的 `exam_scope` 底下是否已經有 `proverb` 題目，如果有就直接中止，不會自動覆蓋或疊加。
- 換到**全新的考試範圍**（例如下一次段考、小考）：直接換一個新的 `--exam-scope` 字串即可，不會跟舊範圍衝突（`question_number` 只在同一個 `(mode, exam_scope)` 內唯一）。匯入後記得手動更新 `active_exam_scope`（見上方「考試範圍設定」）切到新範圍。
- 要**修正／更新**某個 `exam_scope` 已匯入的題庫內容（例如改了幾題的解析）：這支腳本不會做任何刪除，需要手動決定是否清除該範圍的舊資料。動手前務必先查 `attempts_log`／`wrong_question_state` 有沒有已經參照這些題目的作答紀錄——如果有（代表已經有人開始作答這個範圍），刪除前必須先確認清楚，不能直接執行，避免破壞已經產生的研究資料。

**選項文字長度注意事項**：出題卡片的選項並非用 LINE 的 button 元件呈現（button 的可見文字取自 `action.label`，官方硬性限制最多 20 字元，完整句子形式的選項會被截斷），而是改用可完整顯示文字的點擊區塊（box + action，見 [`app/services/flex_templates.py`](app/services/flex_templates.py) 的 `_option_box`）。之後不管哪個模式匯入新題庫，選項文字長度都不受這個限制影響。

### 単語題庫匯入（`scripts/import_vocab_questions.py`）

用途：讀取 `data/raw/` 底下的 Excel 檔案（單一工作表：題目／選項A-D／正確答案），寫入 `questions` 表。這批題目是「詞彙讀音測驗」形式——題目欄位是單一詞彙（例如「短い」），不是情境例句，也沒有解析欄位。

```bash
# 先跑小批次（前 5 個詞）確認流程沒問題
python scripts/import_vocab_questions.py \
    --file "data/raw/檔名.xlsx" --exam-scope "範圍名稱" --limit 5

# 確認沒問題後，正式全量匯入
python scripts/import_vocab_questions.py \
    --file "data/raw/檔名.xlsx" --exam-scope "範圍名稱"
```

重複使用注意事項與 `import_proverb_questions.py` 相同（全量匯入、換範圍要換新的 `--exam-scope`、修改舊資料前要先確認 `attempts_log` 有沒有參照）。

**因為這批資料沒有解析內容，単語模式的回饋機制跟諺／言語知識不同**：単語只考「這個詞怎麼唸」，答對答錯本身沒有需要 AI 說明的細膩語感，所以答題後直接顯示「正確讀音是「〇〇」。」，不呼叫 OpenAI、不寫入 `feedback_logs`。出題卡片因為沒有情境句可以挖空，會多顯示一句「請選出正確讀音」的提示文字（見 `build_question_card` 裡 `mode == "vocab" and not blank_marker` 的判斷）。如果之後単語題庫換成「情境例句挖空＋選項」的格式（沿用 Phase 1 原始設計），需要同時匯入 `explanation_rule` 並把 `_build_feedback_text` 的判斷改回呼叫 AI 生成，目前這個判斷是寫死依 `mode == "vocab"`，不是依「有沒有解析」動態判斷。

### 言語知識題庫匯入（`scripts/import_language_knowledge_questions.py`）

用途：讀取 `data/raw/` 底下的 Excel 檔案，寫入 `questions` 表。跟諺語／単語不同的是，這支腳本支援**同一個檔案裡有多個工作表**，每個工作表都是題目，會依工作表順序合併匯入，`question_number` 跨所有工作表連續編號（不是每個工作表各自從 1 開始）。

實際拿到的題庫裡，不同工作表的欄位結構並不完全一致，腳本會自動適應：
- 選項數：有些工作表只有 A/B/C 三個選項，有些有到 D，腳本依當時實際填寫的「選項X」欄位數量動態判斷，不是寫死 3 或 4 個
- 題目裡的挖空標記：有的用「＿＿」，有的用「（　　）」（全形括號夾兩個全形空格），腳本會逐列用正則判斷這一列實際用的是哪一種；極少數題目本身沒有挖空（是直接問文法用法的題型），這種就不會有 `blank_marker`

```bash
# 先跑小批次（前 5 題，跨工作表累計）確認流程沒問題
python scripts/import_language_knowledge_questions.py \
    --file "data/raw/檔名.xlsx" --exam-scope "範圍名稱" --limit 5

# 確認沒問題後，正式全量匯入
python scripts/import_language_knowledge_questions.py \
    --file "data/raw/檔名.xlsx" --exam-scope "範圍名稱"
```

重複使用注意事項與另外兩支匯入腳本相同（全量匯入、換範圍要換新的 `--exam-scope`、修改舊資料前要先確認 `attempts_log` 有沒有參照）。這批資料有解析內容（格式跟諺語不同，是【文法】【中譯】【正解】【干擾項】而不是【例文】），所以言語知識維持原本 AI 生成回饋的流程，跟単語不同。

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

會建立単語 x2、言語知識 x2、諺 x1 句（3 筆：語意選択／情境選擇／讀音輸入，practice 時前兩者隨機擇一）的最小題庫。接著用測試帳號加官方帳號好友，實際跑一次：

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

**注意：這個字型檔不能用 Git LFS 存放。** 曾經一度改用 LFS 管理這個 5.8MB 的檔案，結果正式環境完成每日挑戰時穩定出現 `OSError: unknown file format`（Pillow 載入字型失敗）——原因是 **Railway 的建置流程不會解析 Git LFS**，抓下來的只是一段 132 bytes 的指標文字，不是真正的字型二進位檔，本機測試因為本機已經 `git lfs pull` 過所以完全看不出問題。5.8MB 遠低於 GitHub 一般檔案 100MB 的上限，所以直接以一般二進位檔案 commit 進 repo（不透過 LFS）即可，不要為了「repo 大小整潔」又把它改回 LFS。

**Railway Cron 設置（每日推播）**：這是一個**獨立的服務**（不是 `hibi-bot` 主服務本身的設定），實際部署時踩過兩個坑，特別列出來：

1. 在 Railway 專案裡新增一個空的服務（Empty Service）專門當這個 cron 用（例如命名「每日挑戰推播」）
2. **這個服務必須指定一個 Docker image 來源**（Settings → Source），例如 `curlimages/curl:latest`——空服務如果沒有指定來源，Railway 沒有東西可以拿來執行 Custom Start Command，`nextCronRunAt` 會一直顯示下次排程時間，但實際上永遠不會真的部署、永遠不會觸發，且不會有任何錯誤提示，容易誤以為設定成功
3. Settings → Deploy → Cron Schedule，設定為每天 UTC 04:00（對應台灣時間 UTC+8 中午 12:00）：
   ```
   0 4 * * *
   ```
4. 這個服務自己的 Variables 裡設定 `INTERNAL_CRON_SECRET`（值要跟 `hibi-bot` 主服務的一致）
5. Settings → Deploy → Custom Start Command，填入對內部端點發送 POST 請求的指令：
   ```bash
   curl -X POST https://<your-railway-app>.up.railway.app/internal/push-daily -H "X-Cron-Secret: $INTERNAL_CRON_SECRET"
   ```
   **注意：`$INTERNAL_CRON_SECRET` 是變數參照語法，要直接照打，不要把它換成任何提示文字或說明文字**——曾經發生過複製指令範例時，把整段「請填入你的密鑰」這種提示文字也一起貼進了實際的 Custom Start Command 欄位，導致每次觸發都用一個不存在的字面字串當密鑰、驗證永遠失敗，而且從 Railway 的角度看部署本身是成功的（服務有正常啟動、執行 curl），只有 log 裡才看得出實際回應是 401，很容易忽略。
6. 本機測試不用等到中午，可以直接手動觸發（伺服器跑在本機、`.env` 已設定 `INTERNAL_CRON_SECRET` 的前提下）：
   ```bash
   curl -X POST http://localhost:8000/internal/push-daily \
     -H "X-Cron-Secret: <你在 .env 設定的值>"
   ```
   回應會是 `{"users": N, "pushed": M}`，`pushed` 是實際成功推播的人數（若某位使用者三個模式當下輪次都沒有剩餘題目，會被排除在外，不視為錯誤）。

跑完後可到 Supabase 後台檢查：
- `daily_challenge`：應新增一筆，`questions` 是決定好的題目順序（最多 5 題，橫跨三模式且不重複），`current_index`／`results`／`completed` 隨作答進度更新
- `push_log`：應新增一筆，`challenge_id` 對應剛才產生的挑戰
- 完成挑戰後，`attempts_log` 裡對應的幾筆應該都有 `daily_challenge_id`（指向這次挑戰）且 `pushed_at` 有值（等於 `push_log.pushed_at`）；相對地，透過「開始練習」自主作答的紀錄 `daily_challenge_id`／`pushed_at` 應維持 `NULL`

## 7. 部署與併發處理

**為什麼需要特別處理併發**：Supabase／OpenAI 的 client 都是同步（非 async）的，webhook 路由雖然宣告成 `async def`，但呼叫這些同步 client 時仍然是阻塞呼叫。如果直接 `await` 呼叫，會讓整個事件迴圈被單一使用者的這次互動整個卡住，導致同時間另一位使用者的請求得排隊等前一位完全處理完（含 AI 生成時間）才能開始處理——多人同時使用時體感會很差，甚至可能造成 LINE webhook 逾時。

因此採用兩層處理：
1. **`app/routers/webhook.py`／`app/routers/internal.py`**：實際處理 postback／文字訊息／每日推播的同步函式，都透過 Starlette 內建的 `run_in_threadpool` 包起來再 `await`，讓事件迴圈可以在等待這些阻塞呼叫時去處理其他使用者的請求，達到真正的併發（同一次 webhook 請求內的多個 event 仍然依序處理，只有跨請求之間才會併發）。
2. **`Procfile`**：`uvicorn --workers 2` 開兩個獨立的 worker process，讓請求可以分散到不同 process 上用多核心真正平行處理。目前設 2 是保守預設值，請依實際 Railway 方案的 CPU／記憶體資源調整（worker 數太多在資源有限的方案上反而可能造成記憶體不足）。

**重要：`app/db/client.py`／`app/services/ai_client.py` 的 client 必須是 thread-local，不能是單一共用實例**。這個環境裝了 `h2`（HTTP/2），Supabase／OpenAI 的底層 httpx client 預設會用 HTTP/2，而 HTTP/2 的連線多工在多個「真正的 OS 執行緒」間共用同一個連線並不安全（只有 async 的單執行緒協作式併發才安全）。改成 `run_in_threadpool` 之後，不同使用者的請求會被丟到不同執行緒平行處理，這時如果所有執行緒共用同一個 client，會穩定重現 `httpx.ReadError: [Errno 35] Resource temporarily unavailable`（已用平行請求實測重現＋修復驗證過）。兩個 client 檔案都用 `threading.local()` 讓每個執行緒各自持有、重複利用自己的 client 實例，之後如果要調整這兩個 client 的建立方式，務必維持這個 thread-local 的設計，不要圖方便改回模組層級的單一共用實例。

**部署到 Railway**：專案根目錄的 `Procfile` 會被 Railway 自動偵測作為啟動指令，不需要額外設定 start command。環境變數（`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`、`SUPABASE_URL`、`SUPABASE_KEY`、`OPENAI_API_KEY`、`INTERNAL_CRON_SECRET` 等，同本機開發設置章節）需要在 Railway 專案的 Variables 裡設定一份。

**Railway 部署地區要跟 Supabase 專案同一個地理區域，不要用預設值**：Railway 預設把服務部署在 `sfo`（舊金山），但這個專案的 Supabase 專案在 `ap-south-1`（孟買）——兩者相距半個地球，會讓每次互動裡的每一次資料庫查詢（單次答題大概 7 次）都多付出一段跨洲延遲，實測後把 Railway 服務改用 `railway service scale southeast-asia=1 sfo=0`（新加坡，Railway 現有選項裡離孟買最近的）解決。之後如果 Supabase 專案換了地區，或是要接新的 Railway 服務，記得先查 `supabase projects list` 確認 Supabase 實際地區，再對應選擇 Railway 的部署地區，不要沿用預設值。OpenAI API 主要在美國，跟 Supabase 兩邊無法同時最佳化時，優先靠近 Supabase——因為單次互動的資料庫來回次數遠多於 AI 呼叫次數。

**併發負載測試（`scripts/load_test_webhook.py`）**：課堂上老師會請全班同時加好友、當場開始使用（一次約 30-40 人併發），實際對正式環境跑過一次驗證：

```bash
python scripts/load_test_webhook.py --concurrency 35 --url https://<your-railway-app>.up.railway.app/webhook
```

用假的 line_user_id 模擬多位使用者同時觸發「下一題」，簽出合法的 LINE webhook 簽章直接打正式環境，量測回應時間，跑完自動清除假使用者留下的所有資料列（`users`／`scope_progress`／`attempts_log` 等）。這是真的會對正式資料庫寫入再刪除資料的操作，不要沒事就跑，只有在預期會有一波真實併發流量（例如課堂當場推廣）之前想確認負載表現時才需要用到。跑出來的結果（35 併發、100% 成功、全部在 3.2 秒內完成）：目前的 2-worker + thread-local client + run_in_threadpool 架構足以應付這個規模，不需要額外調整。

## 8. 測試

**背景**：「查詢使用者作答狀況時，忘記把目前輪次（`round_number`）考慮進去」這類 bug 已經出現過兩次（Phase 5 的單元進度更新、Phase 7 的選題邏輯），兩次都是重置後舊輪次的作答紀錄被誤判成「這輪已經答過」。這類問題單靠人工記得處理不夠可靠，所以補上了自動化回歸測試釘住正確行為。

```bash
python -m pytest tests/ -v
```

`tests/test_round_filtering.py` 針對三個模式（単語／諺／言語知識）各自驗證同一套情境：round 1 作答（含答對、答錯後複習兩種情況）→ 觸發真正的重置流程 → 驗證 round 2 的查詢結果只反映新輪次的狀態，且 round 1 的歷史紀錄在 `attempts_log` 裡完整保留、不受影響。諺語額外驗證 round 2 的候選題目池涵蓋兩種變體（語意選択／文脈穴埋め），不會被 round 1 用過哪個變體侷限住。

測試會建立自己專用的隨機 `exam_scope`（`pytest_<模式>_<亂數>`）跟全新的測試使用者，執行結束後（不管成功或失敗）都會清除自己建立的資料，不會碰到 `active_exam_scope`（正式環境目前教學進度指到的範圍）或任何真實使用者的資料，可以直接對正式的 Supabase 專案跑。

**之後新增任何跟使用者作答狀態有關的查詢邏輯（例如以後如果要加新的統計指標），建議照著 `tests/test_round_filtering.py` 的模式補一組對應測試**——尤其是任何會篩選 `attempts_log`／`wrong_question_state`／`scope_progress` 的新函式，寫完先問自己一次「這個查詢該不該限定在目前這一輪」，是的話就跟著現有測試的情境（作答 → 重置 → 驗證新輪次視角 + 舊輪次歷史保留）補一組測試，養成習慣，不要等到正式資料蒐集期間才發現。

**單語多重正確答案 bug（已修正，2026-07）**：単語題庫第 185 題「異国情緒」的 `correct_option` 被設成 `"a、c"`（兩種讀音都對），但判分邏輯原本假設 `correct_option` 永遠是單一 option id，導致選 a 或 c 都被判「答錯」，回饋文字也直接把 `"a、c"` 這個原始字串印出來、不是真正的讀音。已經新增 `question_picker.is_correct_option()` 統一處理「、」分隔的多重答案（單一答案的題目行為不變）。**這個 bug 曾經造成一位真實使用者的 4 筆歷史作答被誤判**，事後手動修正了他的 `attempts_log`（把選 a、c 那兩筆的 `is_correct` 改成 `True`）跟 `wrong_question_state`（改成 `resolved`，因為他事後證實他其實知道兩種讀音）。如果之後又遇到類似「需要修正已經蒐集的正式資料」的情況：(1) 先查清楚實際受影響的使用者與筆數（不要假設只有眼前這一個案例，要實際查詢確認範圍）(2) 修正前一定要跟研究者確認要怎麼認定「正確答案」，不要自己片面判斷 (3) `wrong_question_state`／`scope_progress` 是獨立於 `attempts_log` 的快取表，修正歷史紀錄不會自動連動更新這兩張表，需要另外手動修正或呼叫 `update_scope_progress()` 刷新。

**PostgREST 預設 1000 筆截斷 bug（已修正，2026-07）**：`get_available_questions_in_scope()`／`count_attempted_in_scope()`／`count_wrong_in_scope()`／`pick_wrong_question()` 這幾個函式原本依 `user_id`（`count_attempted_in_scope` 還多加 `round_number`）查詢 `attempts_log`／`wrong_question_state`，完全沒有分頁，也沒有用 `mode`／`exam_scope` 進一步限縮——這兩張表的查詢條件只有 `user_id`，會把使用者在**三個模式全部歷史**的紀錄都算進同一次查詢，而 PostgREST 單次查詢預設上限是 1000 筆，超過的部分會被悄悄截斷、不會有任何錯誤訊息。實際發生過：一位使用者累積到 1024 筆 `round_number=1` 的作答紀錄後，他最早期（言語知識第 478 題）的那筆作答剛好被截斷在回傳範圍之外，導致系統誤判「這題還沒作答過」，「下一題」持續重複出現同一題，使用者反覆作答了 22 次。已經在 `app/db/client.py` 新增 `fetch_all_rows()`（用 `.range()` 分頁抓好抓滿），套用到這四個函式上。**這類「依 user_id 查詢完全沒有分頁」的寫法要特別小心**：使用者越活躍、用越久，越有可能撞到這個上限，且症狀（重複出現同一題、複習錯題挑不到某些題目）很容易被誤認為是別的問題，不容易第一時間聯想到是分頁截斷。之後新增任何跨模式／跨範圍、依 `user_id` 查詢這兩張表的函式，都要先問自己「這個使用者的歷史筆數會不會隨時間或活躍度成長到超過 1000」，會的話就要用 `fetch_all_rows()`，不要直接 `execute()`。

**諺語多重正確讀音（已修正，2026-07）**：諺語第 2 題「悪事千里を行く」的讀音輸入，老師確認 ゆく／いく 兩種讀音都算正確，但原本 `correct_option` 只設了 `"あくじせんりをゆく"`、判分邏輯也是直接字串相等比對，導致打「いく」的人全部被判答錯。修法跟単語第 185 題那次同一套：`correct_option` 改成 `"あくじせんりをゆく、あくじせんりをいく"`，`message_router.py` 的讀音判分邏輯改呼叫 `is_correct_option()`（原本只給選擇題用，現在讀音輸入這種自由文字比對也共用同一個函式）。**這次規模比単語 185 題那次大很多**：查出來有 11 位不同使用者、共 13 筆歷史作答受影響，且諺語的 `wrong_question_state` 是綁在「第一階段變體的 row id」而非題號本身（同一題號的語意選擇／情境選擇兩種變體各自有獨立的錯題狀態），修正時要對每個受影響的 (user, 變體 id) 組合各自重播完整作答時間序才能得出正確的最終狀態——例如有使用者後來又複習過，中間穿插打錯其他讀音，這種情況不能直接把整個狀態設成「已解決」，要照順序重新走過一次 `finalize_attempt` 的判斷邏輯。修正後也主動呼叫 `update_scope_progress()` 刷新這 11 位使用者的 `scope_progress`，避免有人因為這個已經修正的錯題卡在無法重置。

## 9. 資料安全與備份

**Row Level Security（RLS）**：`app/db/schema.sql` 裡所有的表都已經在 Supabase 開啟 RLS，且刻意不加任何 policy。這個專案後端用的是 `service_role` key（`.env` 的 `SUPABASE_KEY`），這把 key 本來就會完全略過 RLS，所以開啟 RLS 對現有功能沒有任何影響；真正的目的是擋掉 `anon` key（每個 Supabase 專案都有、原本設計給前端用的公開金鑰）——這個專案是純後端架構，從來不需要用到 `anon` key，RLS 關閉只是白白多一個沒必要的暴露面。**如果之後要加任何會員登入、前端直連 Supabase 的功能，需要改用 `anon` key／Supabase Auth，屆時必須額外設計對應的 RLS policy，不能延用現在「零 policy」的設定**，否則前端會完全連不到任何資料。

**免費方案的限制**：這個專案的 Supabase 目前是免費方案，免費方案**沒有自動備份、也沒有時間點還原（PITR）**，而且**閒置超過一週會自動暫停專案**（每天中午的 Cron 推播本身會固定觸發資料庫活動，實務上大幅降低了閒置暫停的風險，但備份的缺口還是要自己補）。升級到 Pro 方案（$25/月）可以拿到「保留 7 天的每日自動備份」，但這個備份**只能在 Supabase 後台一鍵還原，沒辦法下載成檔案存到自己電腦**；PITR 是 Pro 之外的額外付費項目（約 $100/月起）。

**手動備份（`scripts/backup_database.py`）**：不需要額外安裝 Docker 或 pg_dump，直接用專案已經在用的 Supabase Python client，把每張表的資料匯出成 JSON 檔案：

```bash
python scripts/backup_database.py
```

會在 `backups/<時間戳記>/` 底下產生每張表各自的 JSON 檔案（`backups/` 已加進 `.gitignore`，因為裡面是真實使用者資料，絕對不能進公開 repo）。這不是完整的 SQL dump（不含 sequence／function／trigger，這個專案目前也沒有用到這些），但涵蓋所有實際資料列，真的需要復原時的流程是：先用 `app/db/schema.sql` 建好表結構，再把 JSON 資料灌回去。備份頻率目前沒有自動化排程（曾經嘗試用 macOS 的 `launchd` 排程，但這個專案放在「桌面」資料夾，macOS 的隱私保護機制會擋掉背景排程程式的檔案存取，需要手動到「系統設定 → 隱私權與安全性 → 完整磁碟取用權」額外授權才能自動化），目前採取的做法是想到就手動執行一次。

## License

本專案採用 [MIT License](LICENSE)。
