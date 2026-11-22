from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1000, "height": 700})
    context.clear_cookies()
    page = context.new_page()
    
    # 1. Studio Auth Screen - Forgot PIN view
    page.goto("http://127.0.0.1:5000/studio")
    page.wait_for_selector("#auth:not(.hidden)", timeout=5000)
    page.click("#btnForgotPin")
    page.wait_for_timeout(300)
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_studio_forgot_pin.png")
    print("Saved studio forgot pin screenshot")

    # 2. Kiosk Screen - Admin Modal Forgot PIN view
    page.goto("http://127.0.0.1:5000")
    page.wait_for_selector("#s-welcome", timeout=5000)
    page.evaluate("openAdminPinModal()")
    page.wait_for_selector("#adminPinModal:not(.hidden)", timeout=5000)
    page.click("#btnAdminForgotPin")
    page.wait_for_timeout(300)
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_kiosk_forgot_pin.png")
    print("Saved kiosk forgot pin screenshot")
    
    browser.close()
