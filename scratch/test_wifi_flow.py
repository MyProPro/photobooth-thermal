import os
import json
import time
import urllib.parse
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87"

def create_sample_session(sid="test_docs_session"):
    sess_dir = os.path.join("output", "sessions", sid)
    os.makedirs(sess_dir, exist_ok=True)
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 900), color=(30, 41, 59))
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, 570, 870], outline=(245, 158, 11), width=6)
    d.text((120, 420), "ADSBOOTH SOFTCOPY HD", fill=(255, 255, 255))
    img.save(os.path.join(sess_dir, "softcopy_color.jpg"), quality=95)
    img.save(os.path.join(sess_dir, "foto_1.jpg"), quality=92)
    meta = {"id": sid, "event": "thermal-photo-booth", "time": int(time.time()), "number": 99}
    with open(os.path.join(sess_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return sess_dir

def run_tests():
    sid = "test_docs_session"
    create_sample_session(sid)
    wifi_name = "(Wedding Anita & Budi) AdsBooth"
    encoded_wifi = urllib.parse.quote(wifi_name)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 420, "height": 840})

        # 1. Test when host is unreachable (simulating phone on cellular data before connecting to Wi-Fi)
        test_url_unconnected = f"http://127.0.0.1:5000/d#s={sid}&h=http://127.0.0.1:54321&w={encoded_wifi}&exp=5"
        print("Navigating to unconnected flow:", test_url_unconnected)
        page.goto(test_url_unconnected)

        # Wait for #s-wifi to appear
        page.wait_for_selector("#s-wifi.on", timeout=5000)
        wifi_text = page.inner_text("#wifiSsid")
        print("Displayed Wi-Fi SSID:", wifi_text)
        assert wifi_name in wifi_text

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_wifi_connect_prompt.png"))
        print("Saved scratch_wifi_connect_prompt.png")

        # 2. Test when phone connects to Wi-Fi (pointing to real server 127.0.0.1:5000)
        page2 = browser.new_page(viewport={"width": 420, "height": 840})
        test_url_connected = f"http://127.0.0.1:5000/d#s={sid}&h=http://127.0.0.1:5000&w={encoded_wifi}&exp=5"
        print("Navigating to connected flow in page2:", test_url_connected)
        page2.goto(test_url_connected)

        # Should directly reveal the photo (#s-main.on)
        page2.wait_for_selector("#s-main.on", timeout=8000)
        print("Photo successfully revealed on #s-main!")

        page2.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_wifi_photo_revealed.png"))
        print("Saved scratch_wifi_photo_revealed.png")

        browser.close()
        print("All Wi-Fi flow tests passed successfully!")

if __name__ == "__main__":
    run_tests()
