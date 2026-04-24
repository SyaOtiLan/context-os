DROP TABLE IF EXISTS codeforces_contests;
DROP TABLE IF EXISTS codeforces_problems;
DROP TABLE IF EXISTS problem_resources;
DROP TABLE IF EXISTS session_reports;
DROP TABLE IF EXISTS session_events;
DROP TABLE IF EXISTS sessions;

CREATE TABLE IF NOT EXISTS profile_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_facts_category_key
ON profile_facts(category, key);

CREATE TABLE IF NOT EXISTS profile_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL DEFAULT 'rules',
    generated_at TEXT NOT NULL,
    declared_facts_json TEXT NOT NULL,
    recent_projects_json TEXT NOT NULL,
    recent_artifacts_json TEXT NOT NULL,
    activity_status TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profile_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT NOT NULL,
    value TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    title TEXT,
    body TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'project',
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT,
    repo_url TEXT,
    started_at TEXT,
    ended_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    external_id TEXT,
    title TEXT NOT NULL,
    url TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    rating_hint INTEGER,
    tags_json TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunities_source_external_id
ON opportunities(source, external_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    source TEXT,
    metadata_json TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_artifacts_project_id
ON artifacts(project_id);

CREATE TABLE IF NOT EXISTS github_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    state TEXT NOT NULL,
    labels_json TEXT NOT NULL,
    assignees_json TEXT NOT NULL,
    author TEXT,
    body TEXT NOT NULL DEFAULT '',
    is_pull_request INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_github_issues_repo_number
ON github_issues(repo, issue_number);

CREATE INDEX IF NOT EXISTS idx_github_issues_repo_updated_at
ON github_issues(repo, updated_at DESC);

CREATE TABLE IF NOT EXISTS github_issue_filter_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL UNIQUE REFERENCES github_issues(id) ON DELETE CASCADE,
    eligible INTEGER NOT NULL,
    reason_codes_json TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_github_issue_filter_results_eligible
ON github_issue_filter_results(eligible, evaluated_at DESC);

CREATE TABLE IF NOT EXISTS github_issue_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL UNIQUE REFERENCES github_issues(id) ON DELETE CASCADE,
    fit_score INTEGER NOT NULL,
    difficulty TEXT NOT NULL,
    why_fit TEXT NOT NULL,
    why_not_fit TEXT NOT NULL,
    likely_blockers TEXT NOT NULL,
    first_step TEXT NOT NULL,
    should_notify INTEGER NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_github_issue_analyses_should_notify
ON github_issue_analyses(should_notify, analyzed_at DESC);

CREATE TABLE IF NOT EXISTS github_issue_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL REFERENCES github_issues(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_github_issue_notifications_issue_type
ON github_issue_notifications(issue_id, notification_type);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    kind TEXT NOT NULL DEFAULT 'task',
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'todo',
    priority TEXT NOT NULL DEFAULT 'normal',
    due_at TEXT,
    note TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_project_id
ON tasks(project_id);

CREATE INDEX IF NOT EXISTS idx_tasks_opportunity_id
ON tasks(opportunity_id);

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    target TEXT NOT NULL,
    value TEXT NOT NULL,
    rationale TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    starts_at TEXT,
    ends_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_policies_scope_target
ON policies(scope, target);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    service_type TEXT NOT NULL,
    endpoint TEXT,
    owner TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    message TEXT,
    checked_at TEXT NOT NULL,
    latency_ms INTEGER,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_service_checks_service_id
ON service_checks(service_id);
