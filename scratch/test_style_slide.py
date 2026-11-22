from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    
    # 1. Test Welcome / Intro Screen (verify no '&' in introDualBadge)
    page.goto("http://127.0.0.1:5000")
    page.wait_for_selector("#s-welcome")
    page.wait_for_timeout(500)
    
    badge_html = page.inner_html("#introDualBadge")
    print("Intro Dual Badge HTML:", badge_html)
    assert "&amp;" not in badge_html and "&" not in badge_html, "Found '&' in introDualBadge!"
    
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_intro_no_amp.png")
    print("Saved scratch_intro_no_amp.png")

    # 2. Click start, choose 4R Photobooth mode
    page.click("#btnStart")
    page.wait_for_selector(".mode-card[data-mode='photo']", timeout=5000)
    page.click(".mode-card[data-mode='photo']")
    
    # In layout screen, choose Solo
    page.wait_for_selector("#s-layout", timeout=5000)
    page.click("#layoutOptions .opt[data-layout='solo']")
    
    # Now in style screen (4R mode)
    page.wait_for_selector("#s-style", timeout=5000)
    page.wait_for_timeout(800)
    
    # Check style options
    opts = page.locator("#styleOptions .opt")
    count = opts.count()
    print("Photo style card count:", count)
    assert count >= 6, f"Expected at least 6 styles, got {count}"
    
    # Check bounding box of first card
    box1 = opts.nth(0).bounding_box()
    print("Photo Card 1 bounding box:", box1)
    
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_style_photo_slide1.png")
    print("Saved scratch_style_photo_slide1.png")
    
    # Test sliding / clicking next arrow
    next_btn = page.locator("#styleNext")
    if next_btn.is_visible() and not ("off" in (next_btn.get_attribute("class") or "")):
        print("Clicking #styleNext arrow...")
        next_btn.click()
        page.wait_for_timeout(600)
        page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_style_photo_slide2.png")
        print("Saved scratch_style_photo_slide2.png")
        
    # 3. Test Receipt Photobooth mode
    page.goto("http://127.0.0.1:5000")
    page.wait_for_selector("#s-welcome")
    page.click("#btnStart")
    page.wait_for_selector(".mode-card[data-mode='thermal']", timeout=5000)
    page.click(".mode-card[data-mode='thermal']")
    page.wait_for_selector("#s-layout")
    page.click("#layoutOptions .opt[data-layout='solo']")
    page.wait_for_selector("#s-style")
    page.wait_for_timeout(800)
    
    opts_rcpt = page.locator("#styleOptions .opt")
    box_rcpt = opts_rcpt.nth(0).bounding_box()
    print("Receipt Card 1 bounding box:", box_rcpt)
    
    page.screenshot(path=r"C:\Users\Administrator\.gemini\antigravity\brain\c5ff7d34-c116-4183-90d7-c28a52fe5e87\scratch_style_receipt_grid.png")
    print("Saved scratch_style_receipt_grid.png")
    
    # Verify card widths are identical
    print(f"Comparison: Photo width={box1['width']:.1f}px, Receipt width={box_rcpt['width']:.1f}px")
    assert abs(box1['width'] - box_rcpt['width']) < 5, "Card widths differ!"

    browser.close()
print("All verification steps passed successfully!")
