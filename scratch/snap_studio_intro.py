from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 950})
    page.goto("http://127.0.0.1:5000/studio")
    page.wait_for_timeout(1000)
    
    # Check if PIN auth is visible
    auth_input = page.locator("#authPin")
    if auth_input.is_visible():
        print("Logging in with PIN 1234...")
        auth_input.fill("1234")
        page.click("#authBtn")
        page.wait_for_timeout(1000)

    print("Waiting for event list...")
    page.wait_for_selector("#eventList .ev", timeout=10000)
    page.click("#eventList .ev")
    page.wait_for_selector("#introStyle", timeout=10000)
    
    page.locator(".sec:has-text('Layar awal kiosk')").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    out_path = r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_studio_intro.png"
    page.screenshot(path=out_path)
    print("Screenshot saved to", out_path)
    browser.close()
