"""
D2L Notes Downloader
Downloads all unit PDFs for all courses in a semester.

Flow: Login → Course list → Each course → Units → e-Content → Download PDF

Requirements:
    pip install playwright python-dotenv
    playwright install chromium
"""
import asyncio
import os
import re
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG ─────────────────────────────────────────────────────────────────
USERNAME     = os.getenv("UNI_EMAIL")
PASSWORD     = os.getenv("UNI_PASSWORD")
BASE_URL     = "https://learning.onlinemanipal.com"
SEM_TAB      = "BCA_Sem4"
SAVE_DIR     = Path.home() / "Downloads" / f"{SEM_TAB} Notes"
# SAVE_DIR     = Path.home() / "Downloads" / f"BCA Sem-4 Notes"
SESSION_FILE = Path("session.json")
LAB_KEYWORDS = ["lab", "laboratory", "practical"]
# ───────────────────────────────────────────────────────────────────────────


async def login(page):
    print("🔐 Starting login...")
    await page.goto(f"{BASE_URL}/d2l/lp/auth/saml/login")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)

    await page.fill('input[type="email"]', USERNAME)
    await page.get_by_role("button", name="Next").click()
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)
    print("   Email entered ✅")

    await page.fill('input[type="password"]', PASSWORD)
    await page.locator('input[type="submit"], button[type="submit"]').first.click()
    await page.wait_for_load_state("domcontentloaded")
    print("   Password entered ✅")

    print("📱 Approve on your Authenticator app...")
    await page.wait_for_url("**/SAS/ProcessAuth**", timeout=90000)
    await page.wait_for_timeout(1000)
    try:
        await page.get_by_role("button", name="Yes").click(timeout=10000)
    except:
        pass
    await page.wait_for_url("**/d2l/**", timeout=30000)
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)
    print("✅ Logged in!")

def is_lab_course(name: str) -> bool:
    return any(kw in name.lower() for kw in LAB_KEYWORDS)
 
 
async def get_courses(page):
    print(f"\n📚 Fetching courses...")
    await page.goto(f"{BASE_URL}/d2l/home")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)
    links = await page.eval_on_selector_all(
        "a[href*='/d2l/home/']",
        "els => els.map(e => ({ name: e.innerText.trim(), href: e.href }))"
    )
    seen, courses = set(), []
    for link in links:
        name = link["name"].strip()
        href = link["href"]
        course_id = href.rstrip("/").split("/")[-1]
        if href not in seen and name and course_id.isdigit():
            seen.add(href)
            courses.append({"name": name, "href": href, "id": course_id})
    print(f"   Found {len(courses)} course(s)")
    return courses
 
 
async def get_toc_links(page, course_id):
    """
    Use D2L's table of contents API to get all content topics.
    Returns list of { title, url } for topics that have viewable content.
    """
    toc_url = f"{BASE_URL}/d2l/api/le/1.51/{course_id}/content/toc"
    await page.goto(toc_url)
    await page.wait_for_load_state("domcontentloaded")
 
    try:
        content = await page.inner_text("body")
        data = json.loads(content)
    except Exception as e:
        print(f"   ⚠️  Could not parse TOC API: {e}")
        return []
 
    topics = []
    def extract_topics(modules):
        for mod in modules:
            title = mod.get("Title", "")
            # Recurse into sub-modules
            if "Modules" in mod and mod["Modules"]:
                extract_topics(mod["Modules"])
            # Get topics in this module
            for topic in mod.get("Topics", []):
                topic_title = topic.get("Title", "")
                topic_url   = topic.get("Url", "")
                topic_id    = topic.get("TopicId", "")
                topic_type  = topic.get("TypeIdentifier", "")
                topics.append({
                    "title":    topic_title,
                    "url":      topic_url,
                    "id":       topic_id,
                    "type":     topic_type,
                    "module":   title,
                })
 
    if "Modules" in data:
        extract_topics(data["Modules"])
 
    return topics

async def download_pdf_for_topic(page, course_id, topic_id, dest: Path) -> bool:
    pdf_bytes = None
    pdf_received = asyncio.Event()

    async def handle_response(response):
        nonlocal pdf_bytes
        try:
            content_type = response.headers.get("content-type", "")
            url = response.url
            if ("application/pdf" in content_type or
                    "viewFile.d2lfile" in url or
                    "/contentdelivery/" in url or
                    url.endswith(".pdf")):
                body = await response.body()
                if len(body) > 50000:  # must be > 50kb to be a real PDF
                    pdf_bytes = body
                    pdf_received.set()
        except:
            pass

    # Listen on ALL responses including iframes
    page.on("response", handle_response)

    try:
        content_url = f"{BASE_URL}/d2l/le/content/{course_id}/viewContent/{topic_id}/View"
        await page.goto(content_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Wait up to 20 seconds for PDF to load in any frame
        try:
            await asyncio.wait_for(pdf_received.wait(), timeout=20)
        except asyncio.TimeoutError:
            pass

        if pdf_bytes and len(pdf_bytes) > 50000:
            dest.write_bytes(pdf_bytes)
            return True

        # Fallback — click the Download button directly
        try:
            download_btn = page.get_by_role("button", name="Download").first
            if await download_btn.count() > 0:
                async with page.expect_download(timeout=30000) as dl_info:
                    await download_btn.click()
                dl = await dl_info.value
                await dl.save_as(str(dest))
                # Verify file size
                if dest.stat().st_size > 50000:
                    return True
                else:
                    dest.unlink()  # delete corrupt file
                    return False
        except Exception as e:
            print(f"      ⚠️  Download button fallback failed: {e}")

        return False

    finally:
        page.remove_listener("response", handle_response)
 
 
async def download_course_notes(page, course_name, course_id, save_dir: Path):
    """
    Get all content topics via API, filter to e-Content PDFs per unit,
    open each in the viewer, and download.
    """
    course_folder = save_dir / course_name
    course_folder.mkdir(parents=True, exist_ok=True)
    print(f"   📂 {course_folder}")
 
    # Get table of contents via API
    print(f"   📋 Fetching content list via API...")
    topics = await get_toc_links(page, course_id)
    print(f"   Found {len(topics)} total topic(s)")
 
    if not topics:
        print(f"   ⚠️  No topics found — skipping")
        return 0
 
    # Filter to e-Content topics inside Unit modules
    unit_topics = []
    for t in topics:
        module = t["module"].strip().lower()  # strip spaces, lowercase
        title  = t["title"].strip()
        ttype  = t["type"]
        # Only File type topics inside e-Content modules
        if module == "e-content" and ttype == "File":
            unit_topics.append(t)

 
    print(f"   Filtered to {len(unit_topics)} unit e-Content topic(s)")
 
    # Group by unit module
    from collections import defaultdict
    by_unit = defaultdict(list)
    for t in unit_topics:
        by_unit[t["module"]].append(t)
 
    downloaded = 0

    for idx, topic in enumerate(unit_topics, 1):
        # Extract unit number from title e.g. "INS_Unit 01", "DMV Unit 02"
        num_match = re.search(r"Unit\s*[_\-–\s]*(\d+)", topic["title"], re.IGNORECASE)
        unit_num  = num_match.group(1).lstrip("0") if num_match else str(idx)
        clean_title = re.sub(
            r"^[A-Z]+_?Unit\s*0?\d+\s*[-–]?\s*|^PDF\s*[-–]\s*",
            "", topic["title"], flags=re.IGNORECASE
        ).strip()

        if clean_title and len(clean_title) > 2:
            file_name = f"Unit {unit_num} - {clean_title}.pdf"
        else:
            file_name = f"Unit {unit_num}.pdf"
        dest      = course_folder / file_name

        if dest.exists():
            print(f"   ⏭  Already exists: {file_name}")
            continue

        print(f"   📄 {topic['title']} → {file_name}")

        try:
            if page.is_closed():
                print(f"      ⚠️  Page closed — stopping")
                break

            success = await download_pdf_for_topic(page, course_id, topic["id"], dest)

            if success:
                print(f"      ✅ Saved: {file_name}")
                downloaded += 1
            else:
                print(f"      ⚠️  No PDF intercepted — saving debug screenshot")
                await page.screenshot(path=str(course_folder / f"debug_unit{unit_num}.png"))

        except Exception as e:
            if "closed" in str(e).lower():
                print(f"      ⚠️  Page closed — stopping")
                break
            print(f"      ❌ Error: {e}")
            continue
 
    print(f"   ✅ {downloaded} PDF(s) saved for {course_name}")
    return downloaded
 
semaphore = asyncio.Semaphore(2)

async def download_course_notes_tab(browser, context, course_name, course_id, save_dir):
    async with semaphore:
        page = await context.new_page()
        try:
            return await download_course_notes(page, course_name, course_id, save_dir)
        finally:
            await page.close()

async def main():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Saving notes to: {SAVE_DIR}\n")
 
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
 
        if SESSION_FILE.exists():
            print("📂 Loading saved D2L session...")
            context = await browser.new_context(storage_state=str(SESSION_FILE))
        else:
            context = await browser.new_context()
 
        page = await context.new_page()
 
        # Check session
        await page.goto(f"{BASE_URL}/d2l/home")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
 
        if "login" in page.url or "microsoftonline" in page.url:
            print("🔐 Session expired — logging in again...")
            await login(page)
            await context.storage_state(path=str(SESSION_FILE))
            print("💾 Session saved!")
        else:
            print("✅ Session valid, skipping login!")

        courses = await get_courses(page)
        await page.close()

        if not courses:
            print("❌ No courses found")
            await browser.close()
            return

        # Filter out lab courses before timing starts
        filtered = []
        for course in courses:
            raw_name = course["name"].split(",")[0].strip()
            if is_lab_course(raw_name):
                print(f"⏭  Skipping lab course: {raw_name}")
            else:
                course["clean_name"] = raw_name
                filtered.append(course)

        print(f"\n⚡ Downloading {len(filtered)} courses in parallel...\n")

        # Start timer
        start_time = time.perf_counter()

        # Run all courses simultaneously
        tasks = [
            download_course_notes_tab(
                browser,
                context,
                course["clean_name"],
                course["id"],
                SAVE_DIR
            )
            for course in filtered
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Stop timer
        elapsed = time.perf_counter() - start_time

        total = 0
        for r in results:
            if isinstance(r, int):
                total += r
            elif isinstance(r, Exception):
                print(f"⚠️  A course failed: {r}")

        await browser.close()

    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    print(f"\n🎉 Done! {total} PDFs saved to:\n   {SAVE_DIR}")
    print(f"⏱️  Total time: {mins}m {secs}s")
 
if __name__ == "__main__":
    asyncio.run(main())
 