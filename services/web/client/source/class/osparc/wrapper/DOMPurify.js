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
 * @asset(DOMPurify/purify.min.js)
 * @ignore(DOMPurify)
 */

/* global DOMPurify */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/benjamine/jsondiffpatch' target='_blank'>JsonDiffPatch</a>
 */

qx.Class.define("osparc.wrapper.DOMPurify", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "DOMPurify",
    VERSION: "2.0.0",
    URL: "https://github.com/cure53/DOMPurify"
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
    __diffPatcher: null,

    init: function() {
      // initialize the script loading
      let purifyPath = "DOMPurify/purify.min.js";
      let dynLoader = new qx.util.DynamicScriptLoader([
        purifyPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(purifyPath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
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
