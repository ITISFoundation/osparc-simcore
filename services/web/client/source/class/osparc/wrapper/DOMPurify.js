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
      return DOMPurify.sanitize(html);
    }
  }
});
