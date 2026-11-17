from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8766"


def main():
    with httpx.Client(base_url=BASE, trust_env=False, timeout=12) as client:
        queue = client.get("/api/queue").json()
    item = next(entry for entry in queue if entry["status"] in {"queued", "opened"}
                and any(media["kind"] == "video" and media["selected"] and media["ready"]
                        for media in entry["attachments"]))

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "data" / "edge_navigation_live_profile_v127_fixed"),
            channel="msedge", headless=True,
            args=["--disable-extensions-except=" + str(ROOT / "edge-extension"),
                  "--load-extension=" + str(ROOT / "edge-extension")],
        )
        worker = context.service_workers[0] if context.service_workers else (
            context.wait_for_event("serviceworker", timeout=25000))
        extension_id = worker.url.split("/")[2]
        page = context.new_page()
        page.goto(BASE, wait_until="domcontentloaded")
        result = page.evaluate("""async ({extensionId, queueId}) => await new Promise((resolve, reject) => {
          const port = chrome.runtime.connect(extensionId, {name: 'XH_PREPARE_QUEUE_ITEM'});
          const updates = [];
          const timeout = setTimeout(() => reject(new Error('实际 X 页面加载超时')), 80000);
          port.onMessage.addListener((message) => {
            if (message.type === 'progress') updates.push(message.text);
            if (message.type !== 'result') return;
            clearTimeout(timeout);
            port.disconnect();
            resolve({...message, updates});
          });
          port.onDisconnect.addListener(() => reject(new Error(
            chrome.runtime.lastError?.message || '插件发布通道连接中断')));
          port.postMessage({queueId});
        })""", {"extensionId": extension_id, "queueId": item["id"]})
        assert result["updates"][-1] in {
            "正在打开当前 Edge 窗口中的 X 编辑器…",
            "正在把所选 MP4 传送到 X 编辑器…",
        }, result
        assert "Failed to construct 'URL'" not in str(result), result
        assert "Invalid URL" not in str(result), result
        if result["ok"]:
            assert result["video"] is True, result
            assert result["bytes"] > 0, result
        else:
            assert any(value in result["error"] for value in (
                "X", "登录", "页面", "编辑器", "网络", "浏览器",
            )), result
        print("Real X editor navigation response:", result)
        context.close()


if __name__ == "__main__":
    main()
