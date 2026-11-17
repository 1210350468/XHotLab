(() => {
  const VERSION = chrome.runtime.getManifest().version;

  window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    if (event.data?.type !== 'XH_DISCOVER_EXTENSION') return;
    if (typeof event.data.requestId !== 'string') return;

    window.postMessage({
      type: 'XH_EXTENSION_FOUND',
      requestId: event.data.requestId,
      extensionId: chrome.runtime.id,
      version: VERSION,
    }, location.origin);
  });
})();
