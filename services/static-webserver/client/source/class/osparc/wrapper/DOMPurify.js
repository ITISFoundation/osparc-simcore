/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(DOMPurify/purify-3.2.7.min.js)
 * @ignore(DOMPurify)
 */

/* global DOMPurify */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/cure53/DOMPurify' target='_blank'>DOMPurify</a>
 */

qx.Class.define("osparc.wrapper.DOMPurify", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "DOMPurify",
    VERSION: "2.0.0",
    URL: "https://github.com/cure53/DOMPurify",

    sanitizeUrl: function(url) {
      const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(url);
      if ((url && url !== clean) || (clean !== "" && !osparc.utils.Utils.isValidHttpUrl(clean))) {
        osparc.FlashMessenger.logAs(qx.locale.Manager.tr("Error checking link"), "WARNING");
        return null;
      }
      return clean;
    },

    sanitize: function(html) {
      return osparc.wrapper.DOMPurify.getInstance().sanitize(html);
    },

    sanitizeLabel: function(label) {
      label.addListener("changeValue", e => {
        const val = e.getData();
        const sanitized = osparc.wrapper.DOMPurify.sanitize(val);
        if (sanitized !== val) {
          label.setValue(sanitized);
        }
      });
    },
  },

  construct: function() {
    this.base(arguments);
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  members: {
    init: function() {
      return new Promise((resolve, reject) => {
        // initialize the script loading
        const purifyPath = "DOMPurify/purify-3.2.7.min.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          purifyPath
        ]);

        dynLoader.addListenerOnce("ready", e => {
          console.log(purifyPath + " loaded");
          this.setLibReady(true);
          resolve();
        }, this);

        dynLoader.addListener("failed", e => {
          let data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    sanitize: function(html) {
      // https://github.com/markedjs/marked/issues/655#issuecomment-383226346
      // Add a hook to make all links open a new window
      DOMPurify.addHook("afterSanitizeAttributes", function(node) {
        // set all elements owning target to target=_blank
        if ("target" in node) {
          node.setAttribute("target", "_blank");
        }
        // set non-HTML/MathML links to xlink:show=new
        if (
          !node.hasAttribute("target") &&
          (node.hasAttribute("xlink:href") || node.hasAttribute("href"))
        ) {
          node.setAttribute("xlink:show", "new");
        }
      });

      return DOMPurify.sanitize(html);
    }
  }
});
