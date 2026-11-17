from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "edge-extension" / "brand.svg"
OUTPUT = ROOT / "edge-extension" / "icons"


def export_icons() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 256, "height": 256})
        response = page.goto(SOURCE.as_uri())
        assert response is not None and response.ok
        graphic = page.locator("svg")
        graphic.evaluate(
            "element => { element.setAttribute('width', '256'); "
            "element.setAttribute('height', '256'); }"
        )
        source = Image.open(BytesIO(graphic.screenshot())).convert("RGBA")
        browser.close()

    for size in (16, 32, 48, 128):
        target = OUTPUT / f"xhotlab-{size}.png"
        source.resize((size, size), Image.Resampling.LANCZOS).save(target)
        print(f"已生成图标：{target}")


if __name__ == "__main__":
    export_icons()
