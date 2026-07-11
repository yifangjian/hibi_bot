-- 使用者
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_user_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 題目（彈性設計，支援三種模式與諺的多階段結構）
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL CHECK (mode IN ('vocab', 'proverb', 'language_knowledge')),
    exam_scope TEXT NOT NULL,  -- 考試範圍標籤（例如「期中考」「小考3」），純粹分組用，不假設有順序
    stage TEXT,  -- proverb 專用: 'semantic_choice' / 'situational_choice' / 'reading_input'；其他模式為 NULL
    parent_question_id UUID REFERENCES questions(id),  -- 已停用：諺題目改用 question_number 分組（見下方 stage 說明），此欄位保留但不再寫入
    context_sentence TEXT,
    blank_marker TEXT,
    options JSONB,  -- [{"id": "1", "text": "..."}, ...]
    correct_option TEXT,
    explanation_rule TEXT,  -- 人工標註的解釋依據，供 AI 生成回饋時參考，避免自由發揮
    question_number INT,  -- 人類可讀題號，供 AI 助教輸入題號查詢；同一 (mode, exam_scope) 內唯一（不是全域唯一——
                           -- 每次考期換 exam_scope 都會重新從 1 編號，所以題號只在「目前這個範圍」內有意義）
                           -- 単語/言語知識每個題號對應一筆，諺同一題號可有多筆
                           -- （semantic_choice/situational_choice/reading_input 三種 stage 共用同一個 question_number，代表同一句諺語）
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 単語/言語知識：同一 (mode, exam_scope) 下 question_number 唯一；諺：同一 (mode, exam_scope, question_number) 下每個 stage 只能有一筆
-- （用 COALESCE 而非直接 UNIQUE(mode, exam_scope, question_number, stage) 是因為 Postgres 認定兩個 NULL 不算相等，
-- 若用一般 CONSTRAINT，stage 恆為 NULL 的単語/言語知識就會完全失去題號防重複保護）
CREATE UNIQUE INDEX unique_question_number_per_scope_stage ON questions (mode, exam_scope, question_number, COALESCE(stage, ''));

-- 每日挑戰（每天固定時間推播，橫跨三模式隨機抽題，最多 5 題）
CREATE TABLE daily_challenge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    challenge_date DATE NOT NULL,
    questions JSONB NOT NULL,             -- 產生時就決定好的題目順序 [{"mode": "vocab", "question_id": "..."}, ...]
    results JSONB NOT NULL DEFAULT '[]',  -- 已作答部分依序累加 [{"question_id": "...", "is_correct": true}, ...]
    current_index INT NOT NULL DEFAULT 0, -- 目前進行到第幾題（0-based）
    completed BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, challenge_date)
);

-- 永久作答紀錄（只新增不刪除，是研究資料的骨幹）
CREATE TABLE attempts_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    question_id UUID REFERENCES questions(id),
    selected_option TEXT,
    is_correct BOOLEAN,
    attempt_type TEXT CHECK (attempt_type IN ('first', 'review')),
    pushed_at TIMESTAMPTZ,   -- 若為系統推播觸發則有值，使用者自發練習則為 NULL
    responded_at TIMESTAMPTZ DEFAULT now(),
    answer_detail JSONB,  -- 諺兩階段合併判定明細：{stage1_variant, stage1_option, stage1_correct, stage2_reading_input, stage2_correct}；
                          -- stage1_variant 記錄這次隨機抽到的是 semantic_choice 還是 situational_choice，供分析兩種出題形式正確率是否有差異；其他模式為 NULL
    round_number INT NOT NULL DEFAULT 1,  -- 寫入時帶入當下 scope_progress.current_round，供重置後區分輪次
    daily_challenge_id UUID REFERENCES daily_challenge(id)  -- 有值代表這是每日挑戰的一題；使用者自發練習則為 NULL
);

-- 錯題狀態（可變，反映當下的錯題列表）
CREATE TABLE wrong_question_state (
    user_id UUID REFERENCES users(id),
    question_id UUID REFERENCES questions(id),
    status TEXT CHECK (status IN ('wrong', 'resolved')),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, question_id)
);

-- 範圍進度（可變，決定能否重置）
CREATE TABLE scope_progress (
    user_id UUID REFERENCES users(id),
    mode TEXT NOT NULL,
    exam_scope TEXT NOT NULL,
    all_attempted BOOLEAN DEFAULT false,
    all_wrong_resolved BOOLEAN DEFAULT false,
    current_round INT NOT NULL DEFAULT 1,  -- 重置時 +1，並把 all_attempted/all_wrong_resolved 打回 false
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, mode, exam_scope)
);

-- 目前教學進度中的範圍：每個模式同時間只有一個「目前範圍」，由研究者/教師手動指定
-- （目前無管理後台，直接 UPDATE 這張表即可切換範圍，例如換到下一次段考的內容）
CREATE TABLE active_exam_scope (
    mode TEXT PRIMARY KEY,
    exam_scope TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- AI 助教對話輪次限制（僅計入追問，首次解析不計）
CREATE TABLE ai_conversation_usage (
    user_id UUID REFERENCES users(id),
    usage_date DATE NOT NULL,
    turn_count INT DEFAULT 0,
    PRIMARY KEY (user_id, usage_date)
);

-- AI 生成回饋內容留存（供品質檢核與質性分析）
CREATE TABLE feedback_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_log_id UUID REFERENCES attempts_log(id),
    ai_generated_text TEXT,
    model_used TEXT,
    human_reviewed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 圖文選單點擊行為紀錄（研究問題二：練習是否容易啟動的行為訊號）
CREATE TABLE menu_interaction_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    mode TEXT,
    clicked_at TIMESTAMPTZ DEFAULT now()
);

-- 使用者當下等待的文字輸入（諺第二階段讀音輸入／AI 助教題號輸入／AI 助教追問中）
CREATE TABLE user_session_state (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    pending_action TEXT,  -- 'awaiting_reading_input' / 'awaiting_ai_tutor_question_number' / 'in_ai_tutor_conversation' / NULL
    context JSONB,        -- 例如 {"question_id": "...", "mode": "proverb", "first_stage_option": "..."}
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- AI 助教對話逐則紀錄（初次解析與追問皆存於此，供追問時組成對話上下文，亦為質性研究資料）
CREATE TABLE ai_conversation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    question_id UUID REFERENCES questions(id),
    role TEXT CHECK (role IN ('user', 'assistant')),
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 推播事件本身的紀錄（與 attempts_log 分開：使用者可能收到推播卻完全沒回應，
-- 這種「已推播未作答」狀態本身就是研究問題二的重要資料，不能只在作答時才留紀錄）
CREATE TABLE push_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    challenge_id UUID REFERENCES daily_challenge(id),
    pushed_at TIMESTAMPTZ DEFAULT now()
);
