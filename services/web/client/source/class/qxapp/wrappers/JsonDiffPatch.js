/**
 * @asset(jsondiffpatch/jsondiffpatch.*js)
 * @ignore(jsondiffpatch)
 * https://github.com/benjamine/jsondiffpatch
 */

/* global jsondiffpatch */

qx.Class.define("qxapp.wrappers.JsonDiffPatch", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);

    this.init();
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  events: {
    "JsonDiffPatchLibReady": "qx.event.type.Data"
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
        this.fireDataEvent("JsonDiffPatchLibReady", true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.log("failed to load " + data.script);
        this.fireDataEvent("JsonDiffPatchLibReady", false);
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
