import email
import imaplib
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)


class EmailImapCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        host = self.config.get("host", "")
        port = self.config.get("port", 993)
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        folder = self.config.get("folder", "INBOX")
        sender_filter = self.config.get("sender_filter", "")
        max_items = self.config.get("max_items", 20)

        if not host or not username or not password:
            logger.warning(f"Email IMAP config incomplete for {self.source_id}")
            return []

        items = []
        try:
            conn = imaplib.IMAP4_SSL(host, port)
            conn.login(username, password)
            conn.select(folder, readonly=True)

            # Search criteria
            criteria = "UNSEEN"
            if sender_filter:
                criteria = f'(FROM "{sender_filter}")'

            _, msg_ids = conn.search(None, criteria)
            ids = msg_ids[0].split()
            # Take latest N
            ids = ids[-max_items:]

            for mid in ids:
                _, msg_data = conn.fetch(mid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = self._decode_header(msg.get("Subject", ""))
                from_addr = self._decode_header(msg.get("From", ""))
                date_str = msg.get("Date", "")
                message_id = msg.get("Message-ID", "")

                if not subject:
                    continue

                # Extract body
                body = self._extract_body(msg)

                # Parse date
                published_at = None
                if date_str:
                    try:
                        published_at = parsedate_to_datetime(date_str).isoformat()
                    except Exception:
                        pass

                # Use message-id as URL if no link found
                url = f"email://{message_id}" if message_id else f"email://{self.source_id}/{mid.decode()}"

                items.append(CrawledItem(
                    url=url,
                    title=subject,
                    content=body,
                    author=from_addr,
                    published_at=published_at,
                    language=None,
                    media_type="newsletter",
                    raw_metadata={"message_id": message_id, "from": from_addr},
                ))

            conn.close()
            conn.logout()
        except Exception as e:
            logger.error(f"IMAP crawl failed for {self.source_id}: {e}")

        return items

    def _decode_header(self, value: str) -> str:
        if not value:
            return ""
        decoded_parts = email.header.decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)

    def _extract_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
                elif content_type == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html = payload.decode(charset, errors="replace")
                        body = self._html_to_text(html)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    body = self._html_to_text(text)
                else:
                    body = text

        return body.strip()[:5000]

    def _html_to_text(self, html: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
