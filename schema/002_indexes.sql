-- Apply AFTER the first load (index creation is slow on empty tables; pointless, and slow on full tables if done per-row during load)

CREATE INDEX IF NOT EXISTS idx_doctors_state_city     ON providers_doctors (state, city);
CREATE INDEX IF NOT EXISTS idx_doctors_taxonomy       ON providers_doctors (taxonomy_code);
CREATE INDEX IF NOT EXISTS idx_doctors_last_name      ON providers_doctors (last_name);

CREATE INDEX IF NOT EXISTS idx_dentists_state_city    ON providers_dentists (state, city);
CREATE INDEX IF NOT EXISTS idx_dentists_taxonomy      ON providers_dentists (taxonomy_code);
CREATE INDEX IF NOT EXISTS idx_dentists_last_name     ON providers_dentists (last_name);

CREATE INDEX IF NOT EXISTS idx_pharmacists_state_city ON providers_pharmacists (state, city);
CREATE INDEX IF NOT EXISTS idx_pharmacists_taxonomy   ON providers_pharmacists (taxonomy_code);
CREATE INDEX IF NOT EXISTS idx_pharmacists_last_name  ON providers_pharmacists (last_name);

ANALYZE providers_doctors;
ANALYZE providers_dentists;
ANALYZE providers_pharmacists;
