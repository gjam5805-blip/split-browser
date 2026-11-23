// Page ko batao ki extension laga hai, aur screens load hone se pehle tab register karo
(function () {
  const root = document.documentElement;
  const mark = v => { if (document.documentElement) document.documentElement.dataset.msExt = v; };
  if (root) root.dataset.msExt = 'pending';
  chrome.runtime.sendMessage('ms-register', () => {
    void chrome.runtime.lastError;
    mark('ready');
    document.dispatchEvent(new Event('ms-ext-ready'));
  });
})();
