/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(rocketPreview/build/index.html)
 * @asset(rocketPreview/build/**)
 * @asset(rocketPreview/osparc-bridge.js) // build needs to include it
 */

/**
 * A qooxdoo wrapper for The Rocket Preview
 * It loads the app in an iframe and communicates via postMessage.
 */

qx.Class.define("osparc.wrapper.RocketPreview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());

    this.__queue = [];

    // force creation of the iframe child control
    this._createChildControl("iframe");

    window.addEventListener("message", this.__onMessage.bind(this));
  },

  statics: {
    openWindow: function() {
      const win = new osparc.ui.window.Window();
      win.set({
        caption: "Rocket Preview",
        width: 800,
        height: 600,
        minWidth: 400,
        minHeight: 300,
        showMinimize: false,
        showMaximize: false,
        modal: true,
        allowClose: true,
        contentPadding: 0,
        layout: new qx.ui.layout.Grow()
      });

      const rocketPreview = new osparc.wrapper.RocketPreview();
      win.add(rocketPreview);
      win.center();
      win.open();
      return win;
    }
  },

  properties: {
    /**
     * True once the iframe signals it's ready (osparc:ready).
     */
    ready: {
      check: "Boolean",
      init: false,
      event: "changeReady"
    },
  },

  members: {
    __queue: null,
    __iframeEl: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "iframe":
          const src = qx.util.ResourceManager.getInstance().toUri("rocketPreview/build/index.html");
          control = new qx.ui.embed.Html("<iframe></iframe>");
          control.set({
            allowGrowX: true,
            allowGrowY: true
          });

          // configure the real DOM iframe element
          control.addListenerOnce("appear", () => {
            const el = control.getContentElement().getDomElement().querySelector("iframe");
            el.src = src;
            el.style.width = "100%";
            el.style.height = "100%";
            el.style.border = "0";
            this.__iframeEl = el;
          });

          this._add(control, { edge: 0 });
          break;
      }
      return control || this.base(arguments, id);
    },

    // ---- Public API ----
    setTreeData: function(data) {
      this.__send({type: "setTreeData", payload: data});
    },

    setExtraData: function(data) {
      this.__send({type: "setExtraData", payload: data});
    },

    setImage: function(img) {
      this.__send({type: "setImage", payload: img});
    },
    // --------------------

    __send: function(msg) {
      if (!this.isReady()) {
        this.__queue.push(msg);
        return;
      }
      this.__postMessage(msg);
    },

    __onMessage: function(ev) {
      const data = ev.data;
      if (data && data.type === "osparc:ready") {
        this.setReady(true);
        while (this.__queue.length) {
          this.__postMessage(this.__queue.shift());
        }
      }
    },

    __postMessage: function(msg) {
      if (this.__iframeEl && this.__iframeEl.contentWindow) {
        this.__iframeEl.contentWindow.postMessage(msg, "*");
      }
    },
  }
});
