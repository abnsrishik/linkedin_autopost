LinkedIn Autoposter
===================

Telegram bot that creates LinkedIn post drafts with Groq, asks for approval in Telegram, then posts approved drafts to your personal LinkedIn profile.

Local Run
---------

1. Create `.env` from `.env.example`.
2. Install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Run LinkedIn OAuth once:

```bash
python setup_linkedin_oauth.py
```

4. Start bot:

```bash
python run.py
```

Telegram Flow
-------------

- Send any topic or draft to the bot.
- Bot returns a generated LinkedIn post preview.
- Use buttons: Approve, Regenerate, Edit Draft, Cancel.
- Approve posts to the authenticated LinkedIn member profile.
- Bot stays online after posting and waits for next topic.

Commands:

- `/start` or `/help` - reset and show usage.
- `/new` - discard current state and start new post.
- `/cancel` - discard current draft.
- `/status` - show current bot state.

AWS 24/7 Deployment
-------------------

Recommended server: Ubuntu EC2 instance.

Expected app path for included systemd service:

```bash
/home/ubuntu/linkedin-autoposter
```

Install:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
cd /home/ubuntu
git clone <your-repo-url> linkedin-autoposter
cd linkedin-autoposter
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`, then run OAuth:

```bash
./venv/bin/python setup_linkedin_oauth.py
./venv/bin/python healthcheck.py
```

OAuth waits up to 5 minutes for the browser redirect. On a remote server, use an SSH tunnel for port `8080`, or copy the `code` value from the redirect URL and rerun:

```bash
./venv/bin/python setup_linkedin_oauth.py --manual-code <code-from-redirect-url>
```

The app uses LinkedIn's self-serve Share on LinkedIn product. Your LinkedIn app must have these Products enabled:

- Share on LinkedIn, for `w_member_social`
- Sign in with LinkedIn using OpenID Connect, for `openid profile`

The app uses the current LinkedIn Posts API (`rest/posts`) with the `Linkedin-Version: YYYYMM` header. Set `LINKEDIN_VERSION` in `.env` to the current version (e.g., `202604`). Older v2/ugcPosts endpoint is deprecated.

Install always-on service:

```bash
bash scripts/install_service_ubuntu.sh
```

Logs:

```bash
tail -f logs/autoposter.log
journalctl -u linkedin-autoposter -f
```

Do not enable `linkedin-autoposter.timer` for 24/7 mode. The service itself should be enabled.

Security
--------

- Never commit `.env`, `data/`, or `logs/`.
- Rotate any token or secret that was pasted into chat or committed.
- Keep `data/state.db` private because it stores LinkedIn OAuth tokens.
