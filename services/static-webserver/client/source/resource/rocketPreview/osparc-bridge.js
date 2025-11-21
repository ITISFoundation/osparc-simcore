// rocket-bridge.js
(function () {
  const parentWin = window.parent;

  const handlers = {
    setTreeData: async (payload) => {
      console.log("[rocketPreview] setTreeData", payload);
      // TODO
      return {
        ok: true
      };
    },
    setExtraData: async (payload) => {
      console.log("[rocketPreview] setExtraData", payload);
      // TODO
      return {
        ok: true
      };
    },
    setImage: async (payload) => {
      console.log("[rocketPreview] setImage", payload);
      // TODO
      return {
        ok: true
      };
    },
    getState: async () => {
      return {
        status: "ready"
      };
    },
    ping: async (payload) => {
      return {
        pong: true,
        t: payload?.t
      };
    }
  };

  function reply(id, ok, resultOrError) {
    parentWin.postMessage({
      type: "osparc:rpc:result",
      id,
      ok,
      result: ok ? resultOrError : undefined,
      error: ok ? undefined : String(resultOrError)
    }, "*");
  }

  window.addEventListener("message", async (ev) => {
    const data = ev.data;
    if (!data || data.type !== "osparc:rpc") {
      return;
    }
    const { id, action, payload, expectReply } = data;
    try {
      const fn = handlers[action];
      if (typeof fn !== "function") {
        throw new Error(`Unknown action '${action}'`);
      }
      const result = await fn(payload);
      if (expectReply) {
        reply(id, true, result);
      }
    } catch (err) {
      if (expectReply) {
        reply(id, false, err);
      }
    }
  });

  // Tell osparc we’re ready
  window.addEventListener("DOMContentLoaded", () => {
    parentWin.postMessage({
      type: "osparc:ready",
      version: "1.0.0"
    }, "*");
  });
})();
