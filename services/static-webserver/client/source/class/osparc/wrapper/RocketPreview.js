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
 * @asset(rocketPreview/osparc-bridge.js) // index.html needs to include it
 */

/**
 * A qooxdoo wrapper for The Rocket Preview
 * It loads the app in an iframe and communicates via postMessage.
 * NOTES
 * In order to make this work, the Rocket Preview build needs to include the osparc-bridge.js script.
 * Add the following to the index.html
 * <script src="../osparc-bridge.js"></script>
 * Also, the include paths in the index.html need to be adjusted, so that are relative to the index.html.
 */

qx.Class.define("osparc.wrapper.RocketPreview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grow());

    this.__messageQueue = [];

    // force creation of the iframe child control
    this._createChildControl("iframe");

    window.addEventListener("message", this.__onMessage.bind(this));
  },

  statics: {
    NAME: "Sim4Life",
    VERSION: "latest",
    URL: "https://sim4life.swiss/",

    INDEX_HTML: "rocketPreview/build/index.html",

    /**
     * Returns true if the RocketPreview build folder is available as a resource.
     */
    existsBuild: function() {
      const rm = qx.util.ResourceManager.getInstance();
      // index.html is a good proxy for the whole build
      const resourceId = this.INDEX_HTML;
      return rm.has(resourceId);
    },

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
        resizable: true,
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
    rocketReady: {
      check: "Boolean",
      init: false,
      event: "changeReady"
    },
  },

  members: {
    __messageQueue: null,
    __iframeEl: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "iframe":
          const src = qx.util.ResourceManager.getInstance().toUri(this.self().INDEX_HTML);
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

          this._add(control);
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
      if (!this.isRocketReady()) {
        this.__messageQueue.push(msg);
        return;
      }
      this.__postMessage(msg);
    },

    __onMessage: function(ev) {
      const data = ev.data;
      if (data && data.type === "osparc:ready") {
        this.setRocketReady(true);
        while (this.__messageQueue.length) {
          this.__postMessage(this.__messageQueue.shift());
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
