// Page ko batao ki extension laga hai, aur screens load hone se pehle tab register karo.
// Browser abhi abhi khula ho toh extension ka background thodi der me jaagta hai, isliye kuch baar try.
(function () {
  const set = v => { if (document.documentElement) document.documentElement.dataset.msExt = v; };
  set('pending');
  let tries = 0;
  const register = () => {
    tries++;
    chrome.runtime.sendMessage('ms-register', reply => {
      const err = chrome.runtime.lastError;
      if (document.documentElement) document.documentElement.dataset.msExtLast = err ? err.message : String(reply);
      if (!err && reply === 'ok') {
        set('ready');
        document.dispatchEvent(new Event('ms-ext-ready'));
      } else if (tries < 20) {
        setTimeout(register, Math.min(1000, 150 * tries));   // ~12 sec tak try
      } else {
        set('error');
        document.dispatchEvent(new Event('ms-ext-ready'));
      }
    });
  };
  register();
})();
