"""
Email service for sending emails asynchronously
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings


class EmailService:
    """
    Service for sending emails via SMTP
    """
    
    def __init__(self):
        self.host = settings.MAIL_HOST
        self.port = settings.MAIL_PORT
        self.username = settings.MAIL_USERNAME
        self.password = settings.MAIL_PASSWORD
        self.encryption = settings.MAIL_ENCRYPTION
        self.from_address = settings.MAIL_FROM_ADDRESS or settings.MAIL_USERNAME
        self.from_name = settings.MAIL_FROM_NAME
        self.brand_name = settings.MAIL_BRAND_NAME or settings.MAIL_FROM_NAME or "CricGeo"
        self.logo_url = settings.MAIL_LOGO_URL
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def _send_email_sync(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Synchronous email sending (runs in thread pool)
        """
        server = None
        try:
            if not self.host or not self.port:
                print("❌ Email configuration missing: MAIL_HOST/MAIL_PORT is not set")
                return False

            if not self.from_address:
                print("❌ Email configuration missing: MAIL_FROM_ADDRESS (or MAIL_USERNAME) is required")
                return False

            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_address}>"
            message["To"] = to_email
            
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            if self.encryption == "tls":
                server = smtplib.SMTP(self.host, self.port)
                server.starttls()
            elif self.encryption == "ssl":
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
            
            if self.username and self.password:
                server.login(self.username, self.password)

            server.sendmail(self.from_address, to_email, message.as_string())
            
            return True
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {str(e)}")
            return False
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Asynchronous email sending
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._send_email_sync,
            to_email,
            subject,
            html_content,
            text_content
        )
        return result
    
    async def send_otp_email(self, to_email: str, otp_code: str) -> bool:
        """
        Send OTP code for authentication
        """
        subject = f"Your OTP Code - {self.brand_name}"

        logo_markup = (
            f'<img src="{self.logo_url}" alt="{self.brand_name} Logo" '
            'style="width:280px;max-width:88%;height:auto;display:block;margin:0 auto;" />'
            if self.logo_url
            else '<div style="font-weight:900;font-size:32px;letter-spacing:1px;color:#0b2a5b;">CRICGEO</div>'
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;background:#e8edf5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#13233a;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 12px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;border-radius:20px;overflow:hidden;background:#ffffff;box-shadow:0 16px 36px rgba(11,42,91,.18);">
                            <tr>
                                <td style="background:linear-gradient(125deg,#0b2a5b 0%,#1b4cb4 50%,#d91f4b 100%);padding:28px 24px;text-align:center;">
                                    <div style="margin:0 auto 12px auto;">{logo_markup}</div>
                                    <div style="font-size:24px;font-weight:700;color:#ffffff;margin-top:14px;">Verification Code</div>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:36px 32px;">
                                    <p style="margin:0 0 20px 0;font-size:16px;line-height:1.6;color:#3a4c6a;">
                                        Your one-time password (OTP) for {self.brand_name} is:
                                    </p>
                                    <div style="background:linear-gradient(135deg,#f0f4f9 0%,#e1e8f2 100%);border:2px solid #1b4cb4;border-radius:14px;padding:24px;text-align:center;margin:24px 0;">
                                        <div style="font-size:48px;font-weight:900;color:#0b2a5b;letter-spacing:8px;font-family:'Courier New',monospace;">{otp_code}</div>
                                    </div>
                                    <p style="margin:20px 0 10px 0;font-size:15px;color:#5e6e86;">
                                        This code is valid for <strong>5 minutes</strong>.
                                    </p>
                                    <p style="margin:10px 0 0 0;font-size:14px;color:#7c8898;">
                                        If you didn't request this code, please ignore this email.
                                    </p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:16px 28px 22px 28px;border-top:1px solid #e6ebf3;color:#7c8898;font-size:13px;text-align:center;">
                                    © 2026 {self.brand_name}. All rights reserved.
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text_content = (
            f"{self.brand_name} - Verification Code\n\n"
            f"Your OTP code is: {otp_code}\n\n"
            "This code is valid for 5 minutes.\n\n"
            "If you didn't request this code, please ignore this email.\n\n"
            f"© 2026 {self.brand_name}"
        )
        
        return await self.send_email(to_email, subject, html_content, text_content)


# Global email service instance
email_service = EmailService()
