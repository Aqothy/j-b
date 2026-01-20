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
    for job in jobs:
        job_cards += f"""
        <div style="background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #1a202c; line-height: 1.4;">
                    <a href="{job.link}" style="color: #2d3748; text-decoration: none; border-bottom: 1px solid transparent; transition: border-color 0.2s;">
                        {job.title}
                    </a>
                </h3>
            </div>
            
            <div style="margin-bottom: 16px;">
                <p style="margin: 0 0 8px 0; color: #4a5568; font-size: 15px; font-weight: 600; display: flex; align-items: center;">
                    🏢 {job.company}
                </p>
                <p style="margin: 0; color: #718096; font-size: 14px; display: flex; align-items: center;">
                    📍 {job.location}
                </p>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 16px; border-top: 1px solid #edf2f7;">
                <span style="color: #a0aec0; font-size: 12px; font-weight: 500;">
                    {job.source} • {job.date_added or "Recently added"}
                </span>
                <a href="{job.link}" style="display: inline-block; padding: 10px 20px; background: #3182ce; color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 600; transition: background 0.2s;">
                    Apply Now &rarr;
                </a>
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Job Alerts</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f7fafc; padding: 40px 20px; margin: 0; color: #2d3748;">
        <div style="max-width: 600px; margin: 0 auto;">
            
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 40px;">
                <div style="display: inline-block; padding: 12px; background: #ebf8ff; border-radius: 50%; margin-bottom: 16px;">
                    <span style="font-size: 32px;">🚀</span>
                </div>
                <h1 style="margin: 0 0 8px 0; color: #1a202c; font-size: 28px; font-weight: 800; letter-spacing: -0.5px;">Job Scraper Daily</h1>
                <p style="margin: 0; color: #718096; font-size: 16px;">Found <strong style="color: #3182ce;">{len(jobs)}</strong> new opportunities for you</p>
            </div>

            <!-- Job Cards -->
            <div style="margin-bottom: 40px;">
                {job_cards}
            </div>

            <!-- Footer -->
            <div style="text-align: center; border-top: 1px solid #e2e8f0; padding-top: 32px;">
                <p style="margin: 0; color: #a0aec0; font-size: 12px;">
                    Automated Job Scraper • GitHub Actions
                </p>
            </div>
        </div>
    </body>
    </html>
    """
