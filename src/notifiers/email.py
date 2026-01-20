import os
from typing import List

import resend

from src.storage.job_store import Job


def send_job_email(jobs: List[Job], to_email: str) -> bool:
    """Send an email with new job listings."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY not set")
        return False

    resend.api_key = api_key

    # Build HTML email
    html_content = build_email_html(jobs)

    try:
        resend.Emails.send(
            {
                "from": "Job Scraper <onboarding@resend.dev>",
                "to": [to_email],
                "subject": f"🚀 {len(jobs)} New Software Engineering Jobs Found!",
                "html": html_content,
            }
        )
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def build_email_html(jobs: List[Job]) -> str:
    """Build a clean HTML email with job cards."""
    job_cards = ""
    for job in jobs[:20]:  # Limit to 20 jobs per email
        job_cards += f"""
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #ffffff;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a1a;">
                <a href="{job.link}" style="color: #0066cc; text-decoration: none;">{job.title}</a>
            </h3>
            <p style="margin: 4px 0; color: #333; font-weight: 600;">{job.company}</p>
            <p style="margin: 4px 0; color: #666;">📍 {job.location}</p>
            <p style="margin: 4px 0; color: #888; font-size: 12px;">Source: {job.source} • {job.date_added or "Recently added"}</p>
            <a href="{job.link}" style="display: inline-block; margin-top: 8px; padding: 8px 16px; background: #0066cc; color: white; text-decoration: none; border-radius: 4px; font-size: 14px;">Apply Now →</a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; margin: 0;">
        <div style="max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 24px; border-radius: 8px 8px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🎯 New Job Alerts</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">Found {len(jobs)} new software engineering positions</p>
            </div>
            <div style="background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px;">
                {job_cards}
                <p style="text-align: center; color: #888; font-size: 12px; margin-top: 20px;">
                    This email was sent by your Job Scraper running on GitHub Actions.
                    <br>
                    {"Showing first 20 jobs." if len(jobs) > 20 else ""}
                </p>
            </div>
        </div>
    </body>
    </html>
    """
