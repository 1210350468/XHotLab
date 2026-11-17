from playwright.sync_api import sync_playwright
from urllib.parse import parse_qs, urlparse


BASE = "http://127.0.0.1:8766"


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for width, height in ((1360, 650), (1280, 800), (1024, 768), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE, wait_until="domcontentloaded")
            page.locator("#publish-workspace").wait_for(state="visible")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.locator("#advanced-menu summary").click()
            page.locator("#creatorhub-nav").wait_for(state="visible")
            metrics = page.evaluate("""() => {
              const icons = [...document.querySelectorAll('svg.nav-icon')];
              return {
                viewport: innerWidth,
                pageWidth: document.documentElement.scrollWidth,
                iconCount: icons.length,
                iconSizes: icons.map((icon) => {
                  const bounds = icon.getBoundingClientRect();
                  const style = getComputedStyle(icon);
                  return {width: bounds.width, height: bounds.height,
                    fill: style.fill, stroke: style.stroke};
                }),
                navigation: [...document.querySelectorAll('.sidebar .nav-btn')].map((button) => {
                  const bounds = button.getBoundingClientRect();
                  const sidebar = document.querySelector('.sidebar').getBoundingClientRect();
                  return {width: bounds.width, left: bounds.left,
                    sidebarLeft: sidebar.left, sidebarRight: sidebar.right,
                    wordBreak: getComputedStyle(button).wordBreak};
                }),
                cssLink: document.querySelector('link[rel=stylesheet]').href,
                hasIframe: document.querySelectorAll('iframe').length > 0,
              };
            }""")
            assert not errors, errors
            assert metrics["pageWidth"] <= width + 1, metrics
            assert metrics["iconCount"] >= 18, metrics
            assert all(0 <= size["width"] <= 24 and 0 <= size["height"] <= 24
                       and size["fill"] == "none" for size in metrics["iconSizes"]), metrics
            assert all(item["width"] >= (100 if width <= 800 else 140)
                       and item["width"] <= width
                       for item in metrics["navigation"]), metrics
            assert not metrics["hasIframe"], metrics
            assert parse_qs(urlparse(metrics["cssLink"]).query).get("v"), metrics
            print(f"Viewport {width}x{height}: icons, text layout and horizontal bounds OK")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
