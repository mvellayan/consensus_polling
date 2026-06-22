#!/usr/bin/env python3
"""
Supreme Court Case Scraper using Playwright
Scrapes syllabus and opinions from Justia Supreme Court pages
"""

import re
import json
import sys
import asyncio
from playwright.async_api import async_playwright
import time
import numpy as np

def extract_case_number(url):
    """Extract case number from URL"""
    # URL format: https://supreme.justia.com/cases/federal/us/604/22-7466/
    match = re.search(r'/(\d+-\d+)/?$', url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract case number from URL: {url}")


async def extract_syllabus(page):
    """Extract syllabus text between 'Syllabus' and 'Opinions' sections"""
    try:
        # Find the syllabus div and get all text content
        syllabus_div = await page.query_selector('div.block.syllabus')
        if not syllabus_div:
            return None

        # Get the text content from the syllabus section
        text_content = await syllabus_div.inner_text()

        # Clean up the text
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]

        # Remove "Show Less" or "Read More" buttons if present
        lines = [line for line in lines if not line.startswith('Show Less') and not line.startswith('Read More')]

        return '\n\n'.join(lines)
    except Exception as e:
        print(f"Error extracting syllabus: {e}")
        return None


def extract_judge_and_opinion_type(opinion_text):
    """Extract judge name and opinion type from the opinion link text"""
    # Format: "Opinion (Sotomayor)" or "Dissent (Thomas)"
    match = re.search(r'(Opinion|Dissent|Concurrence|Concurring)\s*\(([^)]+)\)', opinion_text, re.IGNORECASE)
    if match:
        opinion_type = match.group(1).lower()
        judge = match.group(2).strip().lower()
        # Clean up judge name - remove any extra spaces
        judge = re.sub(r'\s+', '_', judge)
        return judge, opinion_type
    return None, None


async def extract_opinion_text(page, opinion_id):
    """Extract opinion text from a specific opinion div"""
    try:
        # Wait for the opinion div to be visible
        await page.wait_for_selector(f'#{opinion_id}', state='visible', timeout=5000)

        # Get the opinion div
        opinion_div = await page.query_selector(f'#{opinion_id}')
        if not opinion_div:
            return None

        # Get all text content
        text_content = await opinion_div.inner_text()

        # Find "SUPREME COURT OF THE UNITED STATES" start
        start_marker = "SUPREME COURT OF THE UNITED STATES"
        start_idx = text_content.find(start_marker)

        if start_idx == -1:
            # Try alternative marker
            start_marker = "NOTICE: This opinion is subject to"
            start_idx = text_content.find(start_marker)
            if start_idx == -1:
                print(f"Warning: Could not find start marker in opinion")
                return text_content.strip()

        # Find "Materials" end marker (or end of text)
        text_from_start = text_content[start_idx:]

        # Look for common end markers
        end_markers = ["Materials", "Cite as:", "Supreme Court of the United States", "×"]
        end_idx = -1

        # Don't look for end markers - just return everything after start
        return text_from_start.strip()

    except Exception as e:
        print(f"Error extracting opinion text: {e}")
        return None


async def scrape_supreme_court_case(url):
    """Scrape syllabus and opinions from a Supreme Court case URL"""
    case_number = extract_case_number(url)
    print(f"Scraping case: {case_number}")

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # Load the page
            print(f"Loading URL: {url}")
            await page.goto(url, wait_until='networkidle')

            # Wait for the syllabus to load
            await page.wait_for_selector('div.block.syllabus', timeout=10000)

            # Extract and save syllabus
            print("Extracting syllabus...")
            syllabus = await extract_syllabus(page)
            if syllabus:
                syllabus_file = f"scotus/data/{case_number}_syllabus.json"
                with open(syllabus_file, 'w', encoding='utf-8') as f:
                    json.dump({'syllabus': syllabus}, f, indent=2, ensure_ascii=False)
                print(f"✓ Saved syllabus to {syllabus_file}")
            else:
                print("Warning: Could not extract syllabus")

            # Find all opinion links in the opinions section
            opinion_links = await page.query_selector_all('ul[data-equivalent="opinions-list"] a.nav-item')

            print(f"Found {len(opinion_links)} opinions")

            for link in opinion_links:
                link_text = await link.inner_text()
                judge, opinion_type = extract_judge_and_opinion_type(link_text)

                if not judge or not opinion_type:
                    print(f"Warning: Could not parse opinion link: {link_text}")
                    continue

                # Get the opinion div ID from the link's href
                href = await link.get_attribute('href')
                opinion_id = href.split('#')[-1] if href and '#' in href else None

                if not opinion_id:
                    print(f"Warning: Could not find opinion ID for {link_text}")
                    continue

                print(f"Extracting {opinion_type} by {judge}...")

                try:
                    # Click the link to load the opinion content
                    await link.click()

                    # Wait a moment for content to load
                    await page.wait_for_timeout(500)

                    # Extract opinion text
                    opinion_text = await extract_opinion_text(page, opinion_id)

                    if opinion_text:
                        opinion_file = f"scotus/data/{case_number}_{judge}_{opinion_type}.json"
                        with open(opinion_file, 'w', encoding='utf-8') as f:
                            json.dump({
                                'case_number': case_number,
                                'judge': judge,
                                'opinion_type': opinion_type,
                                'text': opinion_text
                            }, f, indent=2, ensure_ascii=False)
                        print(f"✓ Saved {opinion_type} to {opinion_file}")
                    else:
                        print(f"Warning: Could not extract text for {opinion_type} by {judge}")

                except Exception as e:
                    print(f"Error processing {opinion_type} by {judge}: {e}")
                    continue

            print("\n✓ Scraping completed successfully!")

        finally:
            await browser.close()


def main(url):
    if len(url) < 10:
        print(f"Bad URL? f{url}")
        print("Example: python supreme_court_scraper.py https://supreme.justia.com/cases/federal/us/604/22-7466/")
        sys.exit(1)

    asyncio.run(scrape_supreme_court_case(url))


if __name__ == '__main__':

    # read the file index.json and print out the URL
    with open('scotus/index.json', 'r') as f:
        data = json.load(f)
        for i, url in enumerate(data['index'][10:]):
            print(f"Scraping {i+1}/{len(data)}: {url}")
            # try
            try:
                main(url)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                with open('error.txt', 'a') as f2:
                    f2.write(f"{url}\n")
                continue

            time.sleep(np.random.uniform(7, 12))

