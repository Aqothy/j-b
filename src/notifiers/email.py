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
        <!-- Job Card -->
        <div style="background-color: #ffffff; border-radius: 16px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #edf2f7; overflow: hidden;">
            <div style="padding: 24px;">
                <h3 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #1a202c; line-height: 1.4;">
                    <a href="{job.link}" style="color: #2d3748; text-decoration: none;">{job.title}</a>
                </h3>
                
                <div style="margin-bottom: 24px;">
                    <p style="margin: 0 0 8px 0; color: #4a5568; font-size: 16px; font-weight: 600;">
                        <span style="margin-right: 8px;">🏢</span>{job.company}
                    </p>
                    <p style="margin: 0; color: #718096; font-size: 15px;">
                        <span style="margin-right: 8px;">📍</span>{job.location}
                    </p>
                </div>

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-top: 1px solid #edf2f7; padding-top: 20px;">
                    <tr>
                        <td style="vertical-align: middle;">
                            <p style="margin: 0; color: #a0aec0; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">
                                {job.source}
                            </p>
                            <p style="margin: 4px 0 0 0; color: #cbd5e0; font-size: 12px;">
                                {job.date_added or "Recently added"}
                            </p>
                        </td>
                        <td style="text-align: right; vertical-align: middle;">
                            <a href="{job.link}" style="display: inline-block; padding: 12px 24px; background-color: #3182ce; color: #ffffff; text-decoration: none; border-radius: 10px; font-size: 14px; font-weight: 700; transition: background-color 0.2s;">
                                Apply Now &nbsp;&rarr;
                            </a>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Job Alerts</title>
        <!--[if mso]>
        <style type="text/css">
            body, table, td, a {{ font-family: Arial, Helvetica, sans-serif !important; }}
        </style>
        <![endif]-->
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; padding: 40px 20px; margin: 0; color: #2d3748; -webkit-font-smoothing: antialiased;">
        <div style="max-width: 600px; margin: 0 auto;">
            
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 48px;">
                <div style="display: inline-block; width: 64px; height: 64px; line-height: 64px; background-color: #eff6ff; border-radius: 20px; margin-bottom: 20px; text-align: center;">
                    <span style="font-size: 32px; vertical-align: middle;">🚀</span>
                </div>
                <h1 style="margin: 0 0 12px 0; color: #1a202c; font-size: 32px; font-weight: 800; letter-spacing: -1px;">Job Scraper Daily</h1>
                <p style="margin: 0; color: #64748b; font-size: 18px;">
                    We found <span style="color: #3182ce; font-weight: 700;">{len(jobs)}</span> new opportunities matching your profile.
                </p>
            </div>

            <!-- Job Cards Container -->
            <div style="margin-bottom: 48px;">
                {job_cards}
            </div>

            <!-- Footer -->
            <div style="text-align: center; border-top: 1px solid #e2e8f0; padding-top: 40px;">
                <p style="margin: 0 0 8px 0; color: #94a3b8; font-size: 14px; font-weight: 600;">
                    Automated Job Scraper
                </p>
                <p style="margin: 0; color: #cbd5e0; font-size: 12px;">
                    Running on GitHub Actions • Powered by Resend
                </p>
            </div>
        </div>
    </body>
    </html>
    """
