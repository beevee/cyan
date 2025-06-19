#!/usr/bin/env python3
"""Google Doc Extractor

Downloads a Google Docs document (given a URL), finds every line that contains
only whitespace between square brackets (e.g. "[ ]" or "[   ]"), extracts the
text following the closing bracket, and prints the collected lines.

Usage:
    python main.py "https://docs.google.com/document/d/<DOC_ID>/edit"

Prerequisites:
    • A Google Cloud project with the Google Drive API enabled.
    • A desktop OAuth 2.0 credential JSON saved as `credentials.json` in the
      same directory as this script.

The first run will open a browser window for you to grant access. The obtained
access/refresh token will be cached in `token.json`.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, cast

import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Drive read-only grants us permission to export the document.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_PATH = Path("token.json")
CREDENTIALS_PATH = Path("credentials.json")

# Pattern for checkbox-like list items: capture text before and after the empty brackets.
_CHECKBOX_PATTERN = re.compile(r"(.*?)\[\s*\](.*)")

# Pattern for generic bullet list markers (dash, asterisk, or common unicode bullets).
_BULLET_PATTERN = re.compile(r"^\s*(?:[-*•◦▪]|\d+\.)\s+(.*)")


def extract_doc_id(url: str) -> str:
    """Extracts the Google Docs file ID from URL.

    Args:
        url: Any Google Docs URL, e.g. https://docs.google.com/document/d/<id>/edit

    Returns:
        The file ID string.

    Raises:
        ValueError: If the URL does not appear to contain an ID.
    """

    match = re.search(r"/d/([\w-]{25,})", url)
    if not match:
        raise ValueError("Unable to extract document ID from the provided URL.")
    return match.group(1)


def authenticate() -> Credentials:
    """Obtains user credentials, prompting OAuth flow if necessary."""
    creds: Credentials | None = None

    # Load cached credentials if they exist.
    if TOKEN_PATH.exists():
        creds = cast(Credentials, Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES))

    # Refresh or initiate new OAuth flow if needed.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    "Missing credentials.json. Follow the README to set up OAuth 2.0 credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = cast(Credentials, flow.run_local_server(port=0))

        # Cache the credentials for next run.
        TOKEN_PATH.write_text(creds.to_json())

    # At this point creds is guaranteed to be initialized.
    assert creds is not None
    return creds


def download_document(file_id: str, creds: Credentials) -> str:
    """Downloads the Google Docs document as plain text via Drive 'export'."""
    try:
        service = build("drive", "v3", credentials=creds)
        exported: bytes = (
            service.files()
            .export(fileId=file_id, mimeType="text/plain")
            .execute()
        )
        return exported.decode("utf-8")
    except HttpError as err:
        if err.resp.status == 404:
            raise FileNotFoundError("The requested document was not found or you lack access.") from err
        raise


def build_report(text: str) -> List[str]:
    """Build a hierarchical report of matched lines with their ancestor items.

    The Google Docs plain-text export preserves indentation.  We treat the number
    of leading spaces as the nesting level.  Whenever a list item that matches
    the checkbox pattern is encountered, we output the chain of ancestor items
    (if any) followed by the item itself, each indented two spaces per level.
    """

    output: List[str] = []

    # A stack keeping tuples of (indent_level, item_text).
    stack: List[tuple[int, str]] = []

    collecting = False
    collect_indent: int | None = None
    root_stack_len: int = 0

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue  # Skip empty lines.

        # Normalize tabs → 4 spaces (export usually doesn't contain tabs).
        line = raw_line.expandtabs(4).rstrip("\r\n")

        indent = len(line) - len(line.lstrip(" "))
        content = line.lstrip()

        # Detect whether this line is a bullet or checkbox item.
        checkbox_match = _CHECKBOX_PATTERN.search(content)
        bullet_match = _BULLET_PATTERN.match(content)

        if checkbox_match:
            # Combine any text before and after the empty brackets.
            pre = checkbox_match.group(1).strip()
            post = checkbox_match.group(2).strip()
            # Remove leading bullet markers or numeric enumerations from pre.
            pre_clean = re.sub(r"^(?:[-*•◦▪]|\d+\.)\s*", "", pre)

            if pre_clean and post:
                item_text = f"{pre_clean} {post}"
            else:
                item_text = pre_clean or post
        elif bullet_match:
            # A regular list item (acts as potential ancestor).
            item_text = bullet_match.group(1).strip()
        else:
            continue  # Not a list item – ignore.

        # Adjust the stack to current indentation.
        while stack and indent <= stack[-1][0]:
            # If we're collecting children and popped back to or above the checkbox level, stop collecting.
            if collecting and collect_indent is not None and indent <= collect_indent:
                collecting = False
                collect_indent = None
            stack.pop()

        stack.append((indent, item_text))

        if checkbox_match:
            # Emit path for the checkbox item.
            for level, (_, txt) in enumerate(stack):
                if level == 0:
                    output.append("")  # blank line before new top-level item
                output.append(f"{'  ' * level}- {txt}")

            # Prepare to collect child items.
            collecting = True
            collect_indent = indent
            root_stack_len = len(stack)
            continue  # Process next line

        # If we're collecting children and this line is deeper than checkbox indent.
        if collecting and collect_indent is not None and indent > collect_indent:
            # Output child item with appropriate indentation.
            child_level = len(stack) - 1  # Relative to root
            output.append(f"{'  ' * child_level}- {item_text}")

    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download & parse a Google Docs document for bracket tasks.")
    parser.add_argument("url", help="Google Docs URL")
    parser.add_argument("--telegram", action="store_true", help="Format output for Telegram copy-paste")

    args = parser.parse_args(argv)

    try:
        file_id = extract_doc_id(args.url)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        creds = authenticate()
        raw_text = download_document(file_id, creds)
    except (FileNotFoundError, google.auth.exceptions.GoogleAuthError, HttpError) as exc:
        print(f"Failed to download document: {exc}", file=sys.stderr)
        sys.exit(1)

    report_lines = build_report(raw_text)

    if report_lines:
        if args.telegram:
            tg_text = format_for_telegram(report_lines)
            print(tg_text)
            try:
                copy_to_clipboard(tg_text)
            except Exception:
                pass  # Silently ignore clipboard errors
        else:
            print("\n".join(report_lines))
    else:
        print("No matching lines were found.")


def format_for_telegram(lines: List[str]) -> str:
    """Return a Telegram-friendly formatted string with emojis and indentation.

    We detect indentation (2 spaces == one level) and replace leading "- "
    markers with emoji bullets.
    """

    prefixes = {
        0: "📌",
        1: "🔹",
        2: "🔸",
        3: "▪️",
    }

    formatted: List[str] = [
        "Чтобы на своей шкуре испытать ИИ-редактор кода Cursor, я сделал небольшой скрипт, который скачивает гуглдок с нашими заметками и выводит список не сделанных задач. Заняло около часа, я не написал ни строчки кода. Программисты, видимо, больше не нужны."
    ]
    for raw in lines:
        if not raw.strip():
            formatted.append("")
            continue

        # Count leading spaces in groups of 2
        space_count = len(raw) - len(raw.lstrip(" "))
        level = space_count // 2

        text = raw.lstrip(" -")  # remove leading spaces and dash

        prefix = prefixes.get(level, "▫️")

        # Use non-breaking spaces for indentation so Telegram doesn't collapse.
        indent = "\u00A0" * 2 * level

        formatted.append(f"{indent}{prefix} {text}")

    return "\n".join(formatted)


def copy_to_clipboard(text: str) -> None:
    """Attempts to copy the given text to the OS clipboard."""
    plat = sys.platform
    if plat == "darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
    elif plat.startswith("linux"):
        # Try xclip, then xsel.
        if subprocess.call(["which", "xclip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=False)
        elif subprocess.call(["which", "xsel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=False)
    elif plat.startswith("win"):
        subprocess.run(["clip"], input=text.encode(), check=False)


if __name__ == "__main__":
    main() 