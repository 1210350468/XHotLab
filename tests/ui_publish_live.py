from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8766/"


def main():
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "data" / "edge_publish_live_profile_v129"),
            channel="msedge",
            headless=True,
            args=[
                "--disable-extensions-except=" + str(ROOT / "edge-extension"),
                "--load-extension=" + str(ROOT / "edge-extension"),
            ],
            viewport={"width": 1360, "height": 840},
        )
        worker = context.service_workers[0] if context.service_workers else (
            context.wait_for_event("serviceworker", timeout=25000)
        )
        extension_id = worker.url.split("/")[2]
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE, wait_until="domcontentloaded")
        expect(page.locator("#publish-workspace")).to_be_visible(timeout=25000)
        expect(page.locator("#publish-candidates .publish-candidate").first).to_be_visible()
        assert not page.locator("#advanced-menu").evaluate("node => node.open")
        assert page.locator("#publish-submit").is_enabled()
        assert page.locator("#publish-caption").input_value() == ""
        assert page.locator("#publish-generate").count() == 0
        assert "自动附加" not in page.locator("#publish-workspace").inner_text()
        page.locator("#publish-caption").fill("")
        page.locator("#publish-submit").click()
        expect(page.locator("#publish-guidance-title")).to_have_text("请填写完整的发布文案")
        manual_text = "这条视频里最值得讨论的细节是什么？"
        page.locator("#publish-caption").fill(manual_text)
        assert page.locator("#publish-caption").input_value() == manual_text
        assert page.locator("#publish-attribution").inner_text() == "仅发布你填写的正文"
        expect(page.locator("#publish-character-count")).to_contain_text(
            str(len(manual_text)))
        candidates = page.locator("#publish-candidates .publish-candidate")
        if candidates.count() > 1:
            candidates.nth(1).click()
            assert page.locator("#publish-caption").input_value() == ""
            candidates.first.click()
            assert page.locator("#publish-caption").input_value() == manual_text
        expect(page.locator("#publish-character-count")).to_contain_text("/ 280")

        discovered = page.evaluate("""async () => await new Promise((resolve, reject) => {
          const requestId = crypto.randomUUID();
          const timeout = setTimeout(() => reject(new Error('没有发现实际浏览器扩展')), 5000);
          const onMessage = (event) => {
            if (event.source !== window || event.origin !== location.origin) return;
            if (event.data?.type !== 'XH_EXTENSION_FOUND' || event.data.requestId !== requestId) return;
            clearTimeout(timeout);
            window.removeEventListener('message', onMessage);
            resolve(event.data);
          };
          window.addEventListener('message', onMessage);
          window.postMessage({type: 'XH_DISCOVER_EXTENSION', requestId}, location.origin);
        })""")
        assert discovered['extensionId'] == extension_id, discovered
        assert discovered['version'] == '1.2.9', discovered

        handshake = page.evaluate("""async (extensionId) => await new Promise((resolve) => {
          if (!globalThis.chrome?.runtime?.sendMessage) {
            resolve({error: 'chrome.runtime.sendMessage unavailable'});
            return;
          }
          chrome.runtime.sendMessage(extensionId, {type: 'XH_STATUS'}, (response) => {
            resolve(response || {error: chrome.runtime.lastError?.message});
          });
        })""", extension_id)
        assert handshake == {"ok": True, "version": "1.2.9", "connected": True}, handshake

        invalid_queue = page.evaluate("""async (extensionId) => await new Promise((resolve, reject) => {
          const port = chrome.runtime.connect(extensionId, {name: 'XH_PREPARE_QUEUE_ITEM'});
          const timeout = setTimeout(() => reject(new Error('发布通信超时')), 15000);
          port.onMessage.addListener((message) => {
            if (message?.type !== 'result') return;
            clearTimeout(timeout);
            port.disconnect();
            resolve(message);
          });
          port.onDisconnect.addListener(() => reject(new Error(
            chrome.runtime.lastError?.message || '发布通信意外断开')));
          port.postMessage({queueId: 'xhotlab-publish-connection-probe'});
        })""", extension_id)
        assert invalid_queue["ok"] is False
        assert "发布队列中找不到" in invalid_queue["error"]

        page.locator("#advanced-menu summary").click()
        page.locator("#posts-nav").click()
        expect(page.locator("#publish-workspace")).to_be_hidden()
        page.locator("#publish-nav").click()
        expect(page.locator("#publish-workspace")).to_be_visible()
        assert not errors, errors

        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        context.close()
    print("Unified publish UI passed: real candidates, contextual guidance, real Edge extension messaging, responsive layout.")


if __name__ == "__main__":
    main()
