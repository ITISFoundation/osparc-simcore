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
 * @asset(jsondiffpatch/jsondiffpatch.*js)
 * @ignore(jsondiffpatch)
 */

/* global jsondiffpatch */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/benjamine/jsondiffpatch' target='_blank'>JsonDiffPatch</a>
 */

qx.Class.define("osparc.wrapper.JsonDiffPatch", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "jsondiffpatch",
    VERSION: "0.3.11",
    URL: "https://github.com/benjamine/jsondiffpatch"
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
      let jsondiffpatchPath = "jsondiffpatch/jsondiffpatch.min.js";
      let dynLoader = new qx.util.DynamicScriptLoader([
        jsondiffpatchPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(jsondiffpatchPath + " loaded");

        this.__diffPatcher = jsondiffpatch.create();

        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    diff: function(obj1, obj2) {
      // https://github.com/benjamine/jsondiffpatch/blob/master/docs/deltas.md
      let delta = this.__diffPatcher.diff(obj1, obj2);
      return delta;
    },

    patch: function(obj, delta) {
      this.__diffPatcher.patch(obj, delta);
      return obj;
    },

    // deep clone
    clone: function(obj) {
      return this.__diffPatcher.clone(obj);
    }
  }
});
