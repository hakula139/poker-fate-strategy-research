(() => {
  const info = __LOCAL_CHALLENGE_INFO__;
  if (location.origin !== 'https://accounts.onstove.com') return;

  const reply = (callbackId, value, error = null) => {
    setTimeout(() => {
      window.StoveJSBridge?.callback(callbackId, error, JSON.stringify(value));
    }, 0);
  };

  window._StoveJSBridge = {
    invoke(action, args, callbackId) {
      switch (action) {
        case 'getVersion':
          reply(callbackId, { 'SDK-Version': '2.8.3' });
          break;
        case 'getAllStoveValue':
          reply(callbackId, info.values);
          break;
        case 'getStoveValue':
          reply(callbackId, { key: args, value: info.values[args] ?? '' });
          break;
        case 'getDeviceInfo':
          reply(callbackId, info.device);
          break;
        case 'getValue':
          reply(callbackId, { return_code: 39403, return_message: 'Not Exist Key' });
          break;
        case 'captchaValidated':
          if (typeof args === 'string' && args.length > 0) {
            window.localResearchCaptchaResult(args);
          }
          break;
        case 'closeWebview':
          window.localResearchCaptchaClosed('closed');
          break;
        case 'addLogEvent':
          break;
        default:
          reply(callbackId, null, 'Unsupported local client bridge action');
      }
    },
  };
})();
