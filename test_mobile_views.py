import time
from playwright.sync_api import sync_playwright

def test_mobile():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ================= 1. MOBILE VERTICAL (PORTRAIT: 390x844) =================
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto("http://127.0.0.1:5000/")
        page.wait_for_selector("#btnStart", state="attached")

        # Masuk ke screen style
        page.evaluate("go('style')")
        time.sleep(1.0)
        page.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/c5ff7d34-c116-4183-90d7-c28a52fe5e87/scratch_mobile_portrait_style.png")

        # Masuk ke screen review
        page.evaluate("go('review')")
        time.sleep(2.0)
        dimensions = page.evaluate("""() => {
            const img = document.querySelector('#receiptPreview');
            const stage = document.querySelector('.paper-stage');
            const paper = document.querySelector('.paper');
            const col = document.querySelector('.review-col');
            return {
                img: img ? { w: img.clientWidth, h: img.clientHeight } : null,
                stage: stage ? { w: stage.clientWidth, h: stage.clientHeight } : null,
                paper: paper ? { w: paper.clientWidth, h: paper.clientHeight } : null,
                col: col ? { w: col.clientWidth, h: col.clientHeight } : null
            };
        }""")
        print("Portrait Review Dimensions:", dimensions)
        widths = page.evaluate("""() => ({
            win: window.innerWidth,
            body: document.body.offsetWidth,
            app: document.querySelector('#app').offsetWidth,
            screen: document.querySelector('#s-review').offsetWidth,
            review: document.querySelector('.review').offsetWidth,
            col: document.querySelector('.review-col').offsetWidth
        })""")
        print("Widths:", widths)
        review_style = page.evaluate("""() => {
            const rev = document.querySelector('.review');
            const cs = window.getComputedStyle(rev);
            return {
                display: cs.display,
                flexDirection: cs.flexDirection,
                alignItems: cs.alignItems,
                justifyContent: cs.justifyContent,
                height: cs.height,
                width: cs.width
            };
        }""")
        print("Review Computed Style:", review_style)
        col_style = page.evaluate("""() => {
            const c = document.querySelector('.review-col');
            const w = document.querySelector('.review-preview-wrap');
            const csC = window.getComputedStyle(c);
            const csW = window.getComputedStyle(w);
            return {
                wrap: { h: csW.height, pos: csW.position, flex: csW.flex, margin: csW.margin },
                col: { h: csC.height, pos: csC.position, flex: csC.flex, margin: csC.margin, top: csC.top }
            };
        }""")
        print("Wrap & Col styles:", col_style)
        page.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/c5ff7d34-c116-4183-90d7-c28a52fe5e87/scratch_mobile_portrait_review.png")
        # Screenshot scrolled portrait review
        page.evaluate("document.querySelector('.review').scrollTop = 350")
        time.sleep(0.5)
        page.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/c5ff7d34-c116-4183-90d7-c28a52fe5e87/scratch_mobile_portrait_review_scrolled.png")
        page.close()

        # ================= 2. MOBILE HORIZONTAL (LANDSCAPE: 844x390) =================
        page_ls = browser.new_page(viewport={"width": 844, "height": 390})
        page_ls.goto("http://127.0.0.1:5000/")
        page_ls.wait_for_selector("#btnStart", state="attached")

        # Masuk ke screen style
        page_ls.evaluate("go('style')")
        time.sleep(1.0)
        page_ls.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/c5ff7d34-c116-4183-90d7-c28a52fe5e87/scratch_mobile_landscape_style.png")

        # Masuk ke screen review
        page_ls.evaluate("go('review')")
        time.sleep(2.0)
        page_ls.screenshot(path="C:/Users/Administrator/.gemini/antigravity/brain/c5ff7d34-c116-4183-90d7-c28a52fe5e87/scratch_mobile_landscape_review.png")
        page_ls.close()

        browser.close()
        print("Mobile views tested and captured successfully!")

if __name__ == "__main__":
    test_mobile()
