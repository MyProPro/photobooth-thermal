import json
import urllib.request
from playwright.sync_api import sync_playwright

# Helper to set event output mode
def set_event_output(mode):
    url = "http://127.0.0.1:5000/api/studio/events"
    req = urllib.request.Request(url, headers={"X-Studio-Pin": "1234"})
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    active_id = data["active"]
    
    # Get active event
    ev_url = f"http://127.0.0.1:5000/api/studio/events/{active_id}"
    req_ev = urllib.request.Request(ev_url, headers={"X-Studio-Pin": "1234"})
    ev = json.loads(urllib.request.urlopen(req_ev).read().decode())["event"]
    
    # Update output mode
    ev["output"] = mode
    req_put = urllib.request.Request(ev_url, data=json.dumps(ev).encode(), headers={"Content-Type": "application/json", "X-Studio-Pin": "1234"}, method="PUT")
    urllib.request.urlopen(req_put)
    print(f"Updated event {active_id} output to {mode}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 850})

    # Test 1: Mode Thermal (Receipt)
    set_event_output("thermal")
    page.goto("http://127.0.0.1:5000")
    page.wait_for_selector("#s-welcome")
    page.wait_for_timeout(800)
    
    badge_hidden = page.eval_on_selector("#introDualBadge", "el => el.classList.contains('hidden')")
    prompt_text = page.inner_text("#introPrompt")
    print("Thermal Mode -> Badge hidden:", badge_hidden, "| Prompt:", prompt_text)
    assert badge_hidden is True, "Dual badge should be hidden in thermal mode"
    assert "mulai" in prompt_text and "4R" not in prompt_text
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_intro_auto_thermal.png")

    # Test 2: Mode Photo (4R)
    set_event_output("photo")
    page.goto("http://127.0.0.1:5000")
    page.wait_for_selector("#s-welcome")
    page.wait_for_timeout(800)
    
    badge_hidden = page.eval_on_selector("#introDualBadge", "el => el.classList.contains('hidden')")
    prompt_text = page.inner_text("#introPrompt")
    print("Photo Mode -> Badge hidden:", badge_hidden, "| Prompt:", prompt_text)
    assert badge_hidden is True, "Dual badge should be hidden in photo mode"
    assert "mulai foto" in prompt_text
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_intro_auto_photo.png")

    # Test 3: Mode Both (Dual)
    set_event_output("both")
    page.goto("http://127.0.0.1:5000")
    page.wait_for_selector("#s-welcome")
    page.wait_for_timeout(800)
    
    badge_hidden = page.eval_on_selector("#introDualBadge", "el => el.classList.contains('hidden')")
    prompt_text = page.inner_text("#introPrompt")
    print("Both Mode -> Badge hidden:", badge_hidden, "| Prompt:", prompt_text)
    assert badge_hidden is False, "Dual badge should be visible in both mode"
    assert "memilih" in prompt_text
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_intro_auto_both.png")

    # Test 4: Studio UI Banner
    page.goto("http://127.0.0.1:5000/studio")
    auth_input = page.locator("#authPin")
    if auth_input.is_visible():
        auth_input.fill("1234")
        page.click("#authBtn")
        page.wait_for_timeout(500)
    page.wait_for_selector("#eventList .ev")
    page.click("#eventList .ev")
    page.wait_for_selector("#introAutoBanner")
    page.locator("#introAutoBanner").scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    banner_title = page.inner_text("#introAutoTitle")
    print("Studio Banner Title:", banner_title)
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_studio_auto_intro.png")

    browser.close()

print("All auto intro tests passed successfully!")
