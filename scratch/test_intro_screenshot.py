import os
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87"

def take_intro_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1. Portrait (Tablet/Kiosk)
        page = browser.new_page(viewport={"width": 800, "height": 1280})
        page.goto("http://127.0.0.1:5000/")
        page.wait_for_selector("#s-welcome.active", timeout=10000)
        time.sleep(1)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_intro_portrait_start_here.png"))
        print("Saved scratch_intro_portrait_start_here.png")
        
        # 2. Landscape
        page2 = browser.new_page(viewport={"width": 1280, "height": 800})
        page2.goto("http://127.0.0.1:5000/")
        page2.wait_for_selector("#s-welcome.active", timeout=10000)
        time.sleep(1)
        page2.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_intro_landscape_start_here.png"))
        print("Saved scratch_intro_landscape_start_here.png")
        
        browser.close()

if __name__ == "__main__":
    take_intro_screenshot()
