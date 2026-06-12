ALTER TABLE divinations ADD COLUMN category TEXT;
ALTER TABLE divinations ADD COLUMN client_version TEXT;
ALTER TABLE divinations ADD COLUMN created_date_cn TEXT;

CREATE INDEX IF NOT EXISTS idx_divinations_user_category_time
  ON divinations(user_id, category, created_at DESC);
