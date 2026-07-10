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
    unit_number INT NOT NULL,
    stage TEXT,  -- proverb 專用: 'semantic_choice' / 'situational_choice' / 'reading_input'；其他模式為 NULL
    parent_question_id UUID REFERENCES questions(id),  -- 諺題目：兩階段共用同一個 parent 做關聯
    context_sentence TEXT,
    blank_marker TEXT,
    options JSONB,  -- [{"id": "1", "text": "..."}, ...]
    correct_option TEXT,
    explanation_rule TEXT,  -- 人工標註的解釋依據，供 AI 生成回饋時參考，避免自由發揮
    created_at TIMESTAMPTZ DEFAULT now()
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
    answer_detail JSONB  -- 諺兩階段合併判定明細：{stage1_option, stage1_correct, stage2_reading_input, stage2_correct}；其他模式為 NULL
);

-- 錯題狀態（可變，反映當下的錯題列表）
CREATE TABLE wrong_question_state (
    user_id UUID REFERENCES users(id),
    question_id UUID REFERENCES questions(id),
    status TEXT CHECK (status IN ('wrong', 'resolved')),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, question_id)
);

-- 單元進度（可變，決定能否重置）
CREATE TABLE unit_progress (
    user_id UUID REFERENCES users(id),
    mode TEXT NOT NULL,
    unit_number INT NOT NULL,
    all_attempted BOOLEAN DEFAULT false,
    all_wrong_resolved BOOLEAN DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, mode, unit_number)
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

-- 使用者當下等待的文字輸入（諺第二階段讀音輸入／AI 助教題號輸入）
CREATE TABLE user_session_state (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    pending_action TEXT,  -- 'awaiting_reading_input' / 'awaiting_ai_tutor_question_number' / NULL
    context JSONB,        -- 例如 {"question_id": "...", "mode": "proverb", "first_stage_option": "..."}
    updated_at TIMESTAMPTZ DEFAULT now()
);
