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
    
    async def send_verification_email(self, to_email: str, to_name: str, token: str) -> bool:
        """
        Send email verification link
        """
        verification_url = f"{settings.FRONTEND_URL.rstrip('/')}/auth/verify-email?token={token}"
        subject = f"Verify Your Email - {self.brand_name}"

        logo_markup = (
            f'<img src="{self.logo_url}" alt="{self.brand_name} Logo" '
            'style="height:62px;max-width:260px;object-fit:contain;display:block;margin:0 auto;" />'
            if self.logo_url
            else '<div style="font-weight:900;font-size:36px;letter-spacing:1px;color:#0b2a5b;">CRICGEO</div>'
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;background:#e8edf5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#13233a;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 12px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="680" cellspacing="0" cellpadding="0" style="max-width:680px;border-radius:22px;overflow:hidden;background:linear-gradient(132deg,#0b2a5b 0%,#204aa6 55%,#d91f4b 100%);box-shadow:0 18px 40px rgba(11,42,91,.2);">
                            <tr>
                                <td style="padding:28px 24px 22px 24px;text-align:center;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" align="center" style="background:#ffffff;border-radius:12px;box-shadow:0 10px 22px rgba(8,31,76,.22);">
                                        <tr>
                                            <td style="padding:14px 24px;">{logo_markup}</td>
                                        </tr>
                                    </table>
                                    <div style="font-size:44px;line-height:8px;color:rgba(255,255,255,.22);letter-spacing:7px;margin:12px 0 16px 0;">. . . . . . .</div>
                                    <div style="font-size:46px;font-weight:800;color:#ffffff;line-height:1.18;">Welcome to {self.brand_name}</div>
                                    <div style="margin-top:10px;font-size:23px;color:rgba(255,255,255,.96);font-weight:600;">Live Cricket Score, Smarter.</div>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:0 18px 18px 18px;">
                                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:28px;overflow:hidden;">
                                        <tr>
                                            <td style="padding:34px 34px 16px 34px;">
                                                <h2 style="margin:0 0 14px 0;font-size:26px;line-height:1.2;color:#12316d;">Hi {to_name},</h2>
                                                <p style="margin:0 0 22px 0;font-size:16px;line-height:1.7;color:#3a4c6a;">
                                                    Your account is almost ready. Verify your email to activate your {self.brand_name} account.
                                                </p>
                                                <div style="margin:28px 0 30px 0;text-align:center;">
                                                    <a href="{verification_url}" style="display:inline-block;padding:14px 32px;background:#1b4cb4;color:#ffffff;text-decoration:none;border-radius:14px;font-size:22px;font-weight:800;box-shadow:0 10px 24px rgba(19,67,167,.28);">Verify Email</a>
                                                </div>
                                                <p style="margin:0 0 10px 0;font-size:14px;color:#5e6e86;">If the button does not work, use this link:</p>
                                                <p style="margin:0 0 18px 0;word-break:break-all;font-size:15px;line-height:1.5;"><a href="{verification_url}" style="color:#1b4cb4;">{verification_url}</a></p>
                                                <p style="margin:0 0 10px 0;font-size:14px;color:#5e6e86;">This link expires in 24 hours.</p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding:16px 30px 22px 30px;border-top:1px solid #e6ebf3;color:#7c8898;font-size:13px;text-align:center;">
                                                © 2026 {self.brand_name}. All rights reserved.
                                            </td>
                                        </tr>
                                    </table>
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
            f"Welcome to {self.brand_name}!\n\n"
            f"Hi {to_name},\n\n"
            "Your account is almost ready. Verify your email with this link:\n"
            f"{verification_url}\n\n"
            "This link expires in 24 hours.\n\n"
            f"© 2026 {self.brand_name}"
        )
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_password_reset_email(self, to_email: str, to_name: str, token: str) -> bool:
        """
        Send password reset link
        """
        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        subject = f"Reset Your Password - {self.brand_name}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;background:#edf1f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#13233a;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:28px 14px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px;background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 16px 34px rgba(11,42,91,.16);">
                            <tr>
                                <td style="background:linear-gradient(120deg,#0b2a5b 0%,#143f8f 60%,#cf1d3f 100%);padding:20px 28px;color:#fff;font-size:20px;font-weight:800;text-align:center;">{self.brand_name} Security</td>
                            </tr>
                            <tr>
                                <td style="padding:30px;">
                                    <h2 style="margin:0 0 10px 0;color:#0b2a5b;">Reset password request</h2>
                                    <p style="margin:0 0 18px 0;color:#324761;line-height:1.7;">Hi {to_name}, we received a request to reset your password.</p>
                                    <div style="text-align:center;margin:24px 0;">
                                        <a href="{reset_url}" style="display:inline-block;padding:13px 26px;background:#cf1d3f;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;box-shadow:0 8px 20px rgba(207,29,63,.3);">Reset Password</a>
                                    </div>
                                    <p style="margin:0 0 8px 0;font-size:13px;color:#607089;">If the button does not work, use this link:</p>
                                    <p style="margin:0;word-break:break-all;"><a href="{reset_url}" style="color:#0d3f93;">{reset_url}</a></p>
                                    <p style="margin:18px 0 0 0;font-size:13px;color:#607089;">This link expires in 1 hour.</p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:14px 28px 22px 28px;border-top:1px solid #e9eef5;color:#7b8798;font-size:12px;text-align:center;">© 2026 {self.brand_name}</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text_content = (
            f"{self.brand_name} Security\n\n"
            f"Hi {to_name},\n\n"
            "We received a request to reset your password. Use this link:\n"
            f"{reset_url}\n\n"
            "This link expires in 1 hour.\n\n"
            f"© 2026 {self.brand_name}"
        )
        
        return await self.send_email(to_email, subject, html_content, text_content)


# Global email service instance
email_service = EmailService()
