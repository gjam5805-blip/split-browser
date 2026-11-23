// Multi Screen Helper
// Websites (jaise youtube.com) browser ko bolti hain "mujhe kisi aur page ke andar mat dikhana"
// (X-Frame-Options / CSP frame-ancestors). Ye extension wo line SIRF Multi Screen wale tab ke
// andar ki screens (iframes) ke liye hatata hai. Baaki saari browsing pe koi asar nahi.

const RULE_ID = 1;

async function currentTabs() {
  const rules = await chrome.declarativeNetRequest.getSessionRules();
  const r = rules.find(x => x.id === RULE_ID);
  return r && r.condition.tabIds ? r.condition.tabIds : [];
}

async function setTabs(ids) {
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [RULE_ID],
    addRules: ids.length ? [{
      id: RULE_ID,
      priority: 1,
      action: {
        type: 'modifyHeaders',
        responseHeaders: [
          { header: 'x-frame-options', operation: 'remove' },
          { header: 'content-security-policy', operation: 'remove' },
        ],
      },
      condition: { tabIds: ids, resourceTypes: ['sub_frame'] },
    }] : [],
  });
}

// Multi Screen page khulte hi apna tab register karta hai
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg === 'ms-register' && sender.tab && sender.tab.id >= 0) {
    (async () => {
      const ids = new Set(await currentTabs());
      ids.add(sender.tab.id);
      await setTabs([...ids]);
      reply('ok');
    })();
    return true;
  }
});

chrome.tabs.onRemoved.addListener(async id => {
  const ids = await currentTabs();
  if (ids.includes(id)) await setTabs(ids.filter(x => x !== id));
});
