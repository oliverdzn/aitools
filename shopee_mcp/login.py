"""
One-time Shopee login script.
Run this LOCALLY (not in Docker) to log in to Shopee and save the session.

Usage:
    python login.py
    python login.py --output /path/to/shopee_session.json

After saving, copy shopee_session.json to your server and mount it in Docker:
    volumes:
      - ./shopee_session.json:/app/shopee_session.json:ro
"""
import argparse
import os
from playwright.sync_api import sync_playwright

DEFAULT_OUTPUT = "shopee_session.json"


def main():
    parser = argparse.ArgumentParser(description="Save Shopee login session for the MCP scraper.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output path for session file (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    print("Opening Shopee in a browser window...")
    print("Log in with your Shopee account (handle OTP in the browser), then come back here.\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-PH",
            timezone_id="Asia/Manila",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto("https://shopee.ph/buyer/login")

        input("Press Enter here once you are fully logged in to Shopee...")

        context.storage_state(path=args.output)
        browser.close()

    print(f"\nSession saved to: {os.path.abspath(args.output)}")
    print("Copy this file to your server and mount it at /app/shopee_session.json in Docker.")
    print("Sessions typically last ~30 days before requiring a fresh login.")


if __name__ == "__main__":
    main()
