# Job Scraper

Automated job scraper that monitors GitHub job repositories and emails you new software engineering positions.

## Features

- 🔍 Scrapes [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) for entry-level SWE roles
- 📧 Sends email notifications via [Resend](https://resend.com)
- ⏰ Runs every 30 minutes on GitHub Actions
- 🆕 Tracks seen jobs to only notify about new postings

## Setup

### 1. Fork this repository

### 2. Get a Resend API key

1. Sign up at [resend.com](https://resend.com)
2. Go to [API Keys](https://resend.com/api-keys)
3. Create a new API key

### 3. Add GitHub Secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

| Secret | Description |
|--------|-------------|
| `RESEND_API_KEY` | Your Resend API key |
| `EMAIL_TO` | Your email address |

### 4. Enable GitHub Actions

Go to Actions tab and enable workflows for this repository.

### 5. Test it

Click "Run workflow" manually to test, or wait for the next scheduled run.

## Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/job-scrape.git
cd job-scrape

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API key and email

# Run the scraper
python -m src.main
```

## Project Structure

```
job-scrape/
├── .github/workflows/scrape.yml   # GitHub Actions cron job
├── src/
│   ├── main.py                    # Entry point
│   ├── scrapers/
│   │   └── github_repos.py        # GitHub repo parser
│   ├── notifiers/
│   │   └── email.py               # Resend email sender
│   └── storage/
│       └── job_store.py           # Job deduplication
├── data/
│   └── seen_jobs.json             # Persisted seen job IDs
├── requirements.txt
└── .env.example
```

## How It Works

1. **Scrape**: Fetches README from SimplifyJobs/New-Grad-Positions and parses the HTML table
2. **Deduplicate**: Compares scraped jobs against `data/seen_jobs.json`
3. **Notify**: Sends email with new jobs via Resend
4. **Persist**: Updates `seen_jobs.json` and commits back to repo

## Cost

- **GitHub Actions**: Free (2000 mins/month on free tier)
- **Resend**: Free (100 emails/day)

## Customization

### Add more sources

Edit `src/scrapers/github_repos.py` to add more GitHub repositories.

### Change scrape frequency

Edit `.github/workflows/scrape.yml` and modify the cron schedule:

```yaml
schedule:
  - cron: '0 */2 * * *'  # Every 2 hours instead of 30 mins
```

## License

MIT
