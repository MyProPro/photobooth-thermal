import os
import json
import time
import shutil
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87"

def create_sample_session(sid="test_docs_session"):
    sess_dir = os.path.join("output", "sessions", sid)
    os.makedirs(sess_dir, exist_ok=True)
    
    # Buat foto dummy
    img = Image.new("RGB", (600, 900), color=(30, 41, 59))
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, 570, 870], outline=(245, 158, 11), width=6)
    d.text((120, 420), "ADSBOOTH SOFTCOPY HD", fill=(255, 255, 255))
    img.save(os.path.join(sess_dir, "softcopy_color.jpg"), quality=95)
    img.save(os.path.join(sess_dir, "foto_1.jpg"), quality=92)
    img.save(os.path.join(sess_dir, "foto_2.jpg"), quality=92)
    
    meta = {
        "id": sid,
        "event": "thermal-photo-booth",
        "time": int(time.time()),
        "number": 99
    }
    with open(os.path.join(sess_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return sess_dir

def run_tests():
    sid = "test_docs_session"
    create_sample_session(sid)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 420, "height": 840}) # Mobile viewport
        
        # 1. Test direct visit without code
        page.goto("http://127.0.0.1:5000/d")
        time.sleep(0.5)
        nocode_visible = page.is_visible("#s-nocode")
        print("s-nocode visible:", nocode_visible)
        assert nocode_visible
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_docs_softcopy_nocode.png"))
        print("Saved scratch_docs_softcopy_nocode.png")
        
        # 2. Test preview mode
        page.goto("http://127.0.0.1:5000/d#s=preview")
        time.sleep(0.5)
        preview_visible = page.is_visible("#s-preview")
        print("s-preview visible:", preview_visible)
        assert preview_visible
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_docs_softcopy_preview.png"))
        print("Saved scratch_docs_softcopy_preview.png")
        
        # 3. Test with session hash pointing to booth host
        # Format: #s=<sid>&h=http://127.0.0.1:5000&exp=5
        page.goto(f"http://127.0.0.1:5000/d#s={sid}&h=http://127.0.0.1:5000&exp=5")
        page.wait_for_selector("#s-main.on", timeout=10000)
        time.sleep(0.5)
        
        main_visible = page.is_visible("#s-main")
        print("s-main visible with session:", main_visible)
        assert main_visible
        
        # Check download button
        dl_href = page.get_attribute("#btnDownloadMain", "href")
        print("Download main href:", dl_href)
        assert f"/d/{sid}/softcopy_color.jpg" in dl_href
        
        # Check raw shots count
        raw_items = page.locator(".raw-item").count()
        print("Raw shots count:", raw_items)
        assert raw_items >= 2
        
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_docs_softcopy_main.png"))
        print("Saved scratch_docs_softcopy_main.png")
        
        # 4. Test wifi unreachable screen
        page.goto(f"http://127.0.0.1:5000/d#s={sid}&h=http://192.0.2.1:9999&exp=5")
        time.sleep(3)
        wifi_visible = page.is_visible("#s-wifi")
        print("s-wifi visible when host unreachable:", wifi_visible)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_docs_softcopy_wifi.png"))
        print("Saved scratch_docs_softcopy_wifi.png")
        
        # 5. Test expired screen
        page.goto("http://127.0.0.1:5000/d#s=nonexistent_session&h=http://127.0.0.1:5000&exp=5")
        time.sleep(1)
        expired_visible = page.is_visible("#s-expired")
        print("s-expired visible when session not found:", expired_visible)
        assert expired_visible
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_docs_softcopy_expired.png"))
        print("Saved scratch_docs_softcopy_expired.png")
        
        browser.close()
        print("All docs softcopy tests passed successfully!")

if __name__ == "__main__":
    run_tests()
