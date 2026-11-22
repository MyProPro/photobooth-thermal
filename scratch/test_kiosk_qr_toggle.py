import os
import json
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87"

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        # Test 1: qr_download = True
        with open("events/thermal-photo-booth/event.json", "r", encoding="utf-8") as f:
            ev_data = json.load(f)
        ev_data["qr_download"] = True
        with open("events/thermal-photo-booth/event.json", "w", encoding="utf-8") as f:
            json.dump(ev_data, f, indent=2)
            
        page.goto("http://127.0.0.1:5000/")
        page.wait_for_selector("#s-welcome", timeout=10000)
        
        # Check config from API
        cfg = page.evaluate("() => fetch('/api/config').then(r => r.json())")
        print("API config qr (when True):", cfg.get("qr"))
        assert cfg.get("qr") is True
        
        # Direct render Done screen with QR
        page.evaluate("""() => {
            document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
            document.getElementById('s-done').classList.add('active');
            document.getElementById('qrCard').classList.remove('hidden');
            document.getElementById('qrImg').src = 'http://127.0.0.1:5000/d/test_session_qr_on';
        }""")
        time.sleep(0.5)
        qr_card_hidden = page.evaluate("() => document.getElementById('qrCard').classList.contains('hidden')")
        print("qrCard hidden when qr_download=True:", qr_card_hidden)
        assert not qr_card_hidden
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_kiosk_qr_download_active.png"))
        print("Saved scratch_kiosk_qr_download_active.png")
        
        # Test 2: qr_download = False
        ev_data["qr_download"] = False
        with open("events/thermal-photo-booth/event.json", "w", encoding="utf-8") as f:
            json.dump(ev_data, f, indent=2)
            
        cfg2 = page.evaluate("() => fetch('/api/config').then(r => r.json())")
        print("API config qr (when False):", cfg2.get("qr"))
        assert cfg2.get("qr") is False
        
        # Direct render Done screen without QR
        page.evaluate("""() => {
            document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
            document.getElementById('s-done').classList.add('active');
            document.getElementById('qrCard').classList.add('hidden');
        }""")
        time.sleep(0.5)
        qr_card_hidden2 = page.evaluate("() => document.getElementById('qrCard').classList.contains('hidden')")
        print("qrCard hidden when qr_download=False:", qr_card_hidden2)
        assert qr_card_hidden2
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_kiosk_qr_download_disabled.png"))
        print("Saved scratch_kiosk_qr_download_disabled.png")
        
        # Test 3: Check /d/<sid> when qr_download = False
        res = page.goto("http://127.0.0.1:5000/d/test_session_qr_off")
        print("HTTP status when download disabled:", res.status)
        assert res.status == 403
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_download_disabled_page.png"))
        print("Saved scratch_download_disabled_page.png")
        
        # Restore qr_download = True
        ev_data["qr_download"] = True
        with open("events/thermal-photo-booth/event.json", "w", encoding="utf-8") as f:
            json.dump(ev_data, f, indent=2)
            
        browser.close()
        print("Kiosk QR toggle tests passed successfully!")

if __name__ == "__main__":
    run_tests()
