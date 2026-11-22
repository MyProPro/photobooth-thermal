import os
import json
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87"

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        # 1. Login to Studio
        page.goto("http://127.0.0.1:5000/studio")
        page.wait_for_selector("#authPin", timeout=10000)
        page.fill("#authPin", "1234")
        page.click("#authBtn")
        
        # Wait for #auth to be hidden
        page.wait_for_selector("#auth", state="hidden", timeout=10000)
        print("Studio logged in successfully")
        time.sleep(1)
        
        # Verify downloadUrl input does NOT exist
        has_download_url = page.evaluate("() => !!document.getElementById('downloadUrl')")
        print("has_download_url:", has_download_url)
        assert not has_download_url, "downloadUrl should NOT exist in Studio!"
        
        # Verify qrToggle and downloadAutoDelete exist
        has_qr_toggle = page.evaluate("() => !!document.getElementById('qrToggle')")
        has_auto_delete = page.evaluate("() => !!document.getElementById('downloadAutoDelete')")
        print("has_qr_toggle:", has_qr_toggle, "has_auto_delete:", has_auto_delete)
        assert has_qr_toggle and has_auto_delete
        
        # Scroll down to softcopy section
        page.evaluate("() => document.getElementById('qrToggle').scrollIntoView({ behavior: 'instant', block: 'center' })")
        time.sleep(0.5)
        
        # Make sure qrToggle is checked
        is_checked = page.evaluate("() => document.getElementById('qrToggle').checked")
        if not is_checked:
            page.click("#qrToggle")
            time.sleep(0.3)
            
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_studio_softcopy_checked.png"))
        print("Saved scratch_studio_softcopy_checked.png")
        
        # Now uncheck qrToggle
        page.click("#qrToggle")
        time.sleep(0.3)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "scratch_studio_softcopy_unchecked.png"))
        print("Saved scratch_studio_softcopy_unchecked.png")
        
        # Re-check it and select 5 Menit
        page.click("#qrToggle")
        page.select_option("#downloadAutoDelete", "5")
        time.sleep(0.3)
        
        # Click save
        page.click("#btnSave")
        time.sleep(1)
        
        # Check event.json directly
        with open("events/thermal-photo-booth/event.json", "r", encoding="utf-8") as f:
            ev_data = json.load(f)
        print("Saved event qr_download:", ev_data.get("qr_download"))
        print("Saved event download_auto_delete:", ev_data.get("download_auto_delete"))
        assert ev_data.get("qr_download") is True
        assert ev_data.get("download_auto_delete") == 5
        assert "download_url" not in ev_data
        
        # Also test with qr_download = False
        page.click("#qrToggle")
        time.sleep(0.3)
        page.click("#btnSave")
        time.sleep(1)
        with open("events/thermal-photo-booth/event.json", "r", encoding="utf-8") as f:
            ev_data = json.load(f)
        print("Saved event qr_download after unchecking:", ev_data.get("qr_download"))
        assert ev_data.get("qr_download") is False
        
        # Reset back to True (checked)
        page.click("#qrToggle")
        time.sleep(0.3)
        page.click("#btnSave")
        time.sleep(1)
        with open("events/thermal-photo-booth/event.json", "r", encoding="utf-8") as f:
            ev_data = json.load(f)
        assert ev_data.get("qr_download") is True
        
        browser.close()
        print("All tests passed successfully!")

if __name__ == "__main__":
    run_tests()
