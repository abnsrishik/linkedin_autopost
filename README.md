# LinkedIn Autoposter

Telegram-controlled LinkedIn autoposter that researches current AI topics, drafts posts with Groq, waits for approval, and publishes approved posts to a LinkedIn personal profile.

---

## Overview

LinkedIn Autoposter is an approval-based publishing bot. It runs as a long-lived Telegram polling process, discovers AI-related topics, researches selected topics through multiple providers, generates a LinkedIn post draft with Groq, and publishes only after explicit Telegram approval.

Complete workflow:

```text
Telegram
    |
    v
Create Content
    |
    v
Trending Topics
    |
    v
Research
    |
    v
Ranking
    |
    v
Analysis
    |
    v
Firecrawl enrichment
    |
    v
Jina fallback
    |
    v
ResearchBundle
    |
    v
Groq post generation
    |
    v
Draft Preview
    |
    v
Approve
    |
    v
LinkedIn Publish
```

The bot stores OAuth tokens, workflow state, Telegram offsets, topic choices, and post history in SQLite.

## Features

- Telegram bot workflow with persistent reply keyboard
- Current AI topic discovery
- Multi-provider research through Tavily and SerpAPI
- Research ranking and duplicate removal
- Research cleanup and date normalization
- Firecrawl article enrichment
- Jina Reader fallback when Firecrawl fails
- Compact `ResearchBundle` prompt generation for Groq
- Groq 429 rate-limit detection, retry, and exponential backoff
- Draft preview before publishing
- Edit, regenerate, cancel, and approve actions
- LinkedIn personal-profile publishing
- OAuth setup and Telegram-based reauthorization
- SQLite state, token, history, and Telegram offset persistence
- Render health server when `PORT` is set
- Ubuntu/systemd deployment artifacts
- Structured logging for major runtime stages
- Unit tests for Telegram flow, LinkedIn client, Groq retry handling, OAuth setup, healthcheck, deployment artifacts, and Render health server

## Architecture

```text
Telegram
    |
    v
TelegramHandler
    |
    v
TrendClient
    |
    v
ResearchRouter
    |----------------.
    |                |
    v                v
TavilyProvider   SerpAPIProvider
    |                |
    '-------.--------'
            |
            v
ResearchRanker
            |
            v
ResearchAnalyzer
            |
            v
ResearchCache
            |
            v
FirecrawlProvider
            |
            v
JinaProvider fallback
            |
            v
ResearchBundle
            |
            v
GroqClient
            |
            v
Draft Preview
            |
            v
Approve
            |
            v
LinkedInClient
            |
            v
LinkedIn Posts API
```

Important boundaries:

- `TelegramHandler` orchestrates the user workflow.
- `TrendClient` is a compatibility layer only.
- `ResearchRouter` owns research orchestration.
- Provider code lives under `bot/research/`.
- `GroqClient` consumes strings or `ResearchBundle` objects.
- `LinkedInClient` owns token refresh and publishing.

## Folder Structure

```text
linkedin autoposter/
|-- bot/
|   |-- db.py
|   |-- groq_client.py
|   |-- linkedin_client.py
|   |-- prompts.py
|   |-- render_health_server.py
|   |-- telegram_handler.py
|   |-- trend_client.py
|   |-- __init__.py
|   `-- research/
|       |-- analyzer.py
|       |-- cache.py
|       |-- exceptions.py
|       |-- firecrawl.py
|       |-- jina.py
|       |-- models.py
|       |-- ranker.py
|       |-- router.py
|       |-- serpapi.py
|       |-- tavily.py
|       `-- __init__.py
|-- scripts/
|   |-- bootstrap.sh
|   `-- install_service_ubuntu.sh
|-- tests/
|   |-- test_deployment_artifacts.py
|   |-- test_groq_client.py
|   |-- test_healthcheck.py
|   |-- test_linkedin_client.py
|   |-- test_render_health_server.py
|   |-- test_setup_linkedin_oauth.py
|   |-- test_telegram_flow.py
|   `-- test_trend_client.py
|-- config.py
|-- healthcheck.py
|-- linkedin-autoposter.service
|-- linkedin-autoposter.timer
|-- main.py
|-- run.py
|-- setup_linkedin_oauth.py
|-- requirements.txt
|-- pyproject.toml
|-- uv.lock
`-- .env.example
```

Key files:

| Path | Purpose |
| --- | --- |
| `run.py` | Main entrypoint. Validates config, initializes DB, starts optional health server, starts Telegram polling. |
| `main.py` | Delegates to `run.main()`. |
| `config.py` | Loads environment variables and creates runtime directories. |
| `setup_linkedin_oauth.py` | Performs LinkedIn OAuth setup and stores tokens. |
| `healthcheck.py` | Validates config, database schema, and LinkedIn token state. |
| `bot/db.py` | SQLite schema, tokens, state, history, and Telegram offset persistence. |
| `bot/telegram_handler.py` | Telegram commands, callback handling, draft approval flow. |
| `bot/groq_client.py` | Prompt compression, Groq calls, 429 retry handling, response parsing. |
| `bot/linkedin_client.py` | LinkedIn token refresh and post publishing. |
| `bot/research/` | Research providers, router, models, ranking, analysis, enrichment, cache. |

## Installation

### Requirements

- Python 3.12
- Telegram bot token from BotFather
- Groq API key
- LinkedIn developer app with required products
- Tavily API key for Tavily research
- SerpAPI key for Google News research
- Firecrawl API key for article enrichment

Runtime Python dependencies:

```text
requests==2.31.0
python-dotenv==1.0.1
```

### Clone

```bash
git clone <your-repo-url> linkedin-autoposter
cd linkedin-autoposter
```

### Create Virtual Environment

Linux/macOS:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure Environment

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set the required values.

`SERP_API_KEY` and `FIRECRAWL_API_KEY` are used by the current code. If your `.env.example` does not include them, add them manually:

```env
SERP_API_KEY=
FIRECRAWL_API_KEY=
```

### Initialize LinkedIn OAuth

```bash
python setup_linkedin_oauth.py
```

On a remote server, use manual code mode if the local callback cannot receive LinkedIn's redirect:

```bash
python setup_linkedin_oauth.py --manual-code <code-from-redirect-url>
```

### Run Healthcheck

```bash
python healthcheck.py
```

Expected success:

```text
OK config
OK database schema
OK LinkedIn OAuth token row and member author URN

Healthcheck passed.
```

### Start Bot

```bash
python run.py
```

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from BotFather. |
| `TELEGRAM_USER_ID` | Yes | Authorized Telegram user id. Messages from other chats are ignored. |
| `GROQ_API_KEY` | Yes | Groq API key for post generation. |
| `GROQ_MODEL` | No | Groq model. Defaults to `openai/gpt-oss-120b`. |
| `LINKEDIN_CLIENT_ID` | Yes | LinkedIn developer app client id. |
| `LINKEDIN_CLIENT_SECRET` | Yes | LinkedIn developer app client secret. |
| `LINKEDIN_REDIRECT_URI` | No | OAuth redirect URI. Defaults to `http://localhost:8080/callback`. Must match LinkedIn app settings. |
| `LINKEDIN_VERSION` | No | LinkedIn REST API version header. Defaults to `202604`. |
| `TAVILY_API_KEY` | No, but recommended | Enables Tavily trend and research provider. Without it, Tavily returns no results. |
| `TAVILY_TIME_RANGE` | No | Tavily trend search time range. Defaults to `day`. |
| `TREND_SEARCH_QUERY` | No | Query used for trend discovery. |
| `SERP_API_KEY` | No, but recommended | Enables SerpAPI Google News provider. Without it, SerpAPI returns no results. |
| `FIRECRAWL_API_KEY` | No, but recommended | Enables Firecrawl article enrichment. Without it, Jina fallback is attempted after Firecrawl raises a configuration error. |
| `DB_PATH` | No | SQLite database path. Defaults to `data/state.db`. Use persistent storage in deployment. |
| `PORT` | No | If set, starts a small HTTP health server for Render-style web services. |

Configuration validation requires only Telegram, Groq, and LinkedIn client credentials. Research provider keys are optional in validation but needed for useful trend/research results.

## Configuration

Configuration lives in code constants and environment variables.

| Setting | Location | Current value |
| --- | --- | --- |
| Python version | `.python-version`, `pyproject.toml` | `3.12`, `>=3.12` |
| SQLite DB path | `DB_PATH` env, `config.py` | `data/state.db` default |
| Log path directory | `config.py` | `logs/autoposter.log` path is created; systemd writes there |
| Telegram long poll timeout | `bot/telegram_handler.py` | 20 seconds API timeout, 25 seconds request timeout |
| Telegram send timeout | `bot/telegram_handler.py` | 30 seconds |
| Groq request timeout | `bot/groq_client.py` | 60 seconds |
| Groq max retries after 429 | `bot/groq_client.py` | 3 retries |
| Groq completion limit | `bot/groq_client.py` | 700 tokens |
| Groq prompt article limit | `bot/groq_client.py` | top 3 articles |
| Groq summary truncation | `bot/groq_client.py` | 250 chars |
| Research cache TTL | `bot/research/cache.py` | 30 minutes |
| Tavily max results | `bot/research/tavily.py` | 8 research, 20 trend fetch |
| SerpAPI engine | `bot/research/serpapi.py` | `google_news` |
| Firecrawl timeout | `bot/research/firecrawl.py` | 60 seconds |
| Jina timeout | `bot/research/jina.py` | 60 seconds |
| LinkedIn publish timeout | `bot/linkedin_client.py` | 30 seconds |
| OAuth callback timeout | `setup_linkedin_oauth.py` | 300 seconds |

## Telegram Workflow

The bot exposes a persistent keyboard:

| Button / Command | Behavior |
| --- | --- |
| `Create content` | Fetches three AI topic choices. |
| `Content 1`, `Content 2`, `Content 3` | Selects a topic and starts research + Groq draft generation. |
| `Regenerate Topics` | Fetches a new set of topics. |
| `Approve` | Publishes the current draft to LinkedIn. |
| `Regenerate` | Re-runs research for the current topic and asks Groq for another draft. |
| `Edit Draft` | Waits for edit instructions and revises the current draft. |
| `Cancel` | Discards current workflow and returns to `AWAITING_TOPIC`. |
| `Reauth` | Starts LinkedIn reauthorization inside Telegram. |
| `Status` or `/status` | Shows current workflow state. |
| `/start` or `/help` | Resets state and shows ready message. |
| `/new` or `/reset` | Discards current state and starts a new post. |
| `/cancel` | Discards current draft. |

Manual topic flow is also supported: send any topic or draft text, and the bot generates a LinkedIn draft.

State transitions:

```text
AWAITING_TOPIC
    -> AWAITING_TOPIC_SELECTION
    -> AWAITING_APPROVAL
    -> AWAITING_TOPIC
```

Edit and reauthorization states:

```text
AWAITING_EDIT_INSTRUCTIONS
AWAITING_REAUTH_CODE
```

## Research Pipeline

`TrendClient` delegates to `ResearchRouter`.

Trend discovery:

1. Tavily trend search uses `TREND_SEARCH_QUERY`.
2. SerpAPI uses Google News query `Artificial Intelligence`.
3. Duplicate topic titles are filtered.
4. If fewer than three topics are available, router fills from built-in fallback topic strings.

Research:

1. Provider selection always includes Tavily.
2. SerpAPI is added when topic text contains AI-related keywords such as `ai`, `gpt`, `llm`, `openai`, `anthropic`, `claude`, `gemini`, or `deepmind`.
3. Provider results become `ResearchArticle` objects.
4. Ranker removes duplicate URLs and near-duplicate titles.
5. Ranker scores articles based on content, summary, answer, and trusted domains.
6. Analyzer cleans whitespace, removes boilerplate, trims content to 4000 chars, and normalizes known date formats.
7. Router checks in-memory cache by URL.
8. Firecrawl scrapes article content.
9. Jina Reader is used when Firecrawl raises `FirecrawlError`.
10. Results are returned as a `ResearchBundle`.

Current data models:

```text
TrendingTopic(title, url, provider, published, metadata)
ResearchArticle(title, url, provider, summary, content, domain, published, answer, score, language, fetched_at, metadata)
ResearchBundle(query, articles, providers, created_at)
```

## Groq Integration

Groq post generation is handled by `bot/groq_client.py`.

Implemented behavior:

- Accepts plain text or `ResearchBundle`.
- Uses only the top 3 ranked articles.
- Truncates summaries to 250 characters.
- Omits metadata from prompts.
- Keeps research prompt content compact.
- Logs estimated prompt size.
- Uses `include_reasoning=False`.
- Uses `reasoning_effort=low`.
- Uses `max_completion_tokens=700`.
- Detects HTTP 429.
- Parses retry duration from Groq error text, for example `try again in 1.5s`.
- Falls back to `Retry-After` header when needed.
- Waits `retry_time + 1` seconds, then uses exponential backoff.
- Retries 3 times before returning a graceful runtime error.
- Handles timeout, connection errors, invalid JSON, unexpected response schemas, and empty drafts.

The Telegram workflow catches Groq errors and sends a readable error message instead of crashing the polling loop.

## LinkedIn Publishing

LinkedIn publishing targets a personal LinkedIn profile.

Required LinkedIn app products:

- Share on LinkedIn, for `w_member_social`
- Sign in with LinkedIn using OpenID Connect, for `openid profile`

OAuth setup:

1. `setup_linkedin_oauth.py` builds an authorization URL with scopes `openid profile w_member_social`.
2. It receives a callback on `LINKEDIN_REDIRECT_URI`, or accepts `--manual-code`.
3. It exchanges the authorization code for tokens.
4. It calls `/v2/userinfo`.
5. It stores `urn:li:person:{sub}` as `author_urn`.

Publishing:

1. `LinkedInClient.publish_post()` checks token state.
2. If access token expires within 5 minutes, it refreshes token when refresh token exists and is valid.
3. It posts to `https://api.linkedin.com/rest/posts`.
4. It sends `Linkedin-Version` and `X-Restli-Protocol-Version` headers.
5. It expects HTTP `201`.
6. It reads `x-restli-id` / `X-RestLi-Id` as the post URN.
7. Telegram receives a success message with a LinkedIn feed URL.

The code rejects non-person author URNs for publishing.

## Database

SQLite is initialized automatically by `init_db()`.

Default path:

```text
data/state.db
```

Tables:

| Table | Purpose |
| --- | --- |
| `tokens` | LinkedIn OAuth tokens, expiry, author URN, author type. |
| `state` | Telegram workflow state, selected topic, current draft, topic choices. |
| `history` | Published captions and LinkedIn URNs. |
| `bot_meta` | Telegram polling offset. |

Keep `data/state.db` private. It contains OAuth tokens.

## Deployment

### Local Long-Running Bot

```bash
python run.py
```

### Render-Style Web Service

If `PORT` is set, the bot starts a small health server:

```json
{"ok": true, "service": "linkedin-autoposter"}
```

The Telegram polling loop still runs in the same process.

Use persistent storage for SQLite:

```env
DB_PATH=/var/data/state.db
```

After deployment, send `Reauth` in Telegram so tokens are stored in the deployed database.

### Ubuntu/systemd

Included service expects:

```text
/home/ubuntu/linkedin-autoposter
```

Bootstrap a server:

```bash
bash scripts/bootstrap.sh
```

Then configure `.env`, run OAuth, run healthcheck, and install service:

```bash
python setup_linkedin_oauth.py
python healthcheck.py
bash scripts/install_service_ubuntu.sh
```

Service logs:

```bash
tail -f logs/autoposter.log
journalctl -u linkedin-autoposter -f
```

The timer file exists, but the current always-on bot uses `linkedin-autoposter.service`. Do not enable `linkedin-autoposter.timer` for 24/7 Telegram operation.

## Error Handling

| Area | Behavior |
| --- | --- |
| Telegram polling | Message and callback handlers catch unexpected exceptions and notify the user. |
| Research providers | Provider exceptions are logged; other providers continue. |
| Trending topics | Router falls back to built-in topics if providers return too few topics. |
| Empty research | Telegram reports no usable articles and asks user to regenerate or choose a more specific topic. |
| Firecrawl | Raises `FirecrawlError`; router tries Jina fallback. |
| Jina | Failure is logged; article remains with whatever content was already available. |
| Groq 429 | Retry duration parsed, wait applied, exponential backoff, up to 3 retries. |
| Groq network/schema errors | Raised as readable runtime errors and caught by Telegram workflow. |
| LinkedIn token expiry | Access token refresh attempted when refresh token exists and is valid. |
| LinkedIn publish failure | Status code and response body included in error. Draft remains available for retry. |

## Testing

Run all tests:

```bash
python -m unittest discover -s tests -v
```

Run Groq retry tests:

```bash
python -m unittest tests.test_groq_client -v
```

Run Telegram workflow tests:

```bash
python -m unittest tests.test_telegram_flow -v
```

Run LinkedIn client tests:

```bash
python -m unittest tests.test_linkedin_client -v
```

Run compile check:

```bash
python -m compileall bot run.py main.py config.py
```

Run healthcheck:

```bash
python healthcheck.py
```

Expected test result:

```text
OK
```

The test suite uses mocks for external services. Live end-to-end publishing requires real Telegram, Groq, research provider, Firecrawl/Jina, and LinkedIn credentials.

## Logging

`run.py` configures Python logging:

```text
%(asctime)s %(levelname)s %(name)s %(message)s
```

Logged stages include:

- Telegram send/edit/poll/callback/generate/publish
- Research trending/provider/rank/analyze/enrichment/cache
- Provider HTTP status codes
- Groq prompt size, retries, response status, final usage
- LinkedIn refresh and publish status

Local logs go to standard output. The systemd service appends stdout and stderr to:

```text
logs/autoposter.log
```

## Troubleshooting

### `Missing required environment variables`

Run:

```bash
python healthcheck.py
```

Then set every missing variable in `.env`.

### Telegram bot does not respond

Check:

- `TELEGRAM_BOT_TOKEN` is correct.
- `TELEGRAM_USER_ID` is your numeric Telegram user id.
- Bot process is running.
- Only the configured user id is allowed.

Run:

```bash
python run.py
```

### Create Content returns fallback topics only

Tavily and SerpAPI may be missing, invalid, or failing.

Check:

```env
TAVILY_API_KEY=
SERP_API_KEY=
```

Then inspect logs for:

```text
stage=research.trending
stage=provider.tavily.trending
stage=provider.serpapi.trending
```

### Research completes but no draft is generated

Likely causes:

- Providers returned no usable article URLs.
- Firecrawl and Jina both failed.
- Groq returned an error.

Use a more specific topic or tap `Regenerate Topics`.

### Groq rate limit: HTTP 429

The bot now retries automatically. Logs show:

```text
stage=groq.rate_limit status=retry
```

If retries are exhausted, wait and try again. To reduce pressure further, lower topic frequency or switch to a higher Groq rate limit plan.

### Groq timeout or empty draft

The bot reports a readable Telegram error. Logs include:

```text
stage=groq.api
stage=groq.prompt
```

Prompt compression is already enabled. If errors persist, verify `GROQ_MODEL` and Groq account limits.

### LinkedIn OAuth tokens missing

Run:

```bash
python setup_linkedin_oauth.py
python healthcheck.py
```

On deployed servers, send `Reauth` in Telegram and paste the returned authorization code.

### LinkedIn refresh token expired

Run OAuth again:

```bash
python setup_linkedin_oauth.py
```

Or send `Reauth` to the Telegram bot.

### LinkedIn publish fails

Check:

- LinkedIn app has Share on LinkedIn enabled.
- OAuth scopes include `w_member_social`.
- `author_urn` starts with `urn:li:person:`.
- `LINKEDIN_VERSION` is accepted by LinkedIn.

Logs include LinkedIn response status and response body.

### Database corruption or wrong environment database

Verify `DB_PATH`:

```bash
python -c "from config import DB_PATH; print(DB_PATH)"
```

For deployment, use persistent storage. If tokens were set up locally but bot runs on server, reauthorize on the server or set `DB_PATH` to the correct persisted path.

### PowerShell profile parse errors

If PowerShell prints errors before commands run, fix your user PowerShell profile. This is outside the bot code, but it can make command output noisy.

## Current Limitations

- Publishes only to LinkedIn personal profiles, not organization pages.
- Uses Telegram long polling, not webhooks.
- Research provider keys are optional in validation, but useful live research needs Tavily and/or SerpAPI.
- In-memory research cache resets when the process restarts.
- No automatic scheduling is implemented in the bot workflow.
- `.env.example` may not list every optional research key used by current code; add `SERP_API_KEY` and `FIRECRAWL_API_KEY` manually if missing.
- Groq output is prompted to be 900-1200 characters, but the code does not enforce character count after generation.

## Roadmap

Future improvements that fit the current architecture:

- Add enforced post-length validation after Groq generation.
- Add provider health diagnostics to `healthcheck.py`.
- Persist research cache across restarts.
- Add explicit integration test harness for live provider calls.
- Add configurable Groq token budgets through environment variables.
- Add a documented release/deployment checklist.

## Contributing

1. Create a branch.
2. Make a focused change.
3. Run tests:

```bash
python -m unittest discover -s tests -v
python -m compileall bot run.py main.py config.py
```

4. Update documentation when behavior changes.
5. Open a pull request with:
   - Problem statement
   - Summary of changes
   - Verification commands and results
   - Any known limitations

Do not commit `.env`, `data/`, `logs/`, or OAuth tokens.

## License

No license file is currently present in this repository. Add a license before publishing or accepting external contributions.

## Acknowledgements

This project uses:

- Telegram Bot API
- Groq Chat Completions API
- LinkedIn OAuth and Posts API
- Tavily Search API
- SerpAPI Google News
- Firecrawl
- Jina Reader
- Python `requests`
- Python `python-dotenv`
- SQLite
