/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(jsontreeviewer/jsonTree.*)
 * @asset(jsontreeviewer/icons.svg)
 * @ignore(jsonTree)
 */

/* global jsonTree */

qx.Class.define("qxapp.wrappers.JsonTreeViewer", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "jsonTreeViewer",
    VERSION: "0.6.0",
    URL: "https://github.com/summerstyle/jsonTreeViewer"
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
      // initialize the script loading
      let jsonTreeViewerPath = "jsontreeviewer/jsonTree.js";
      let jsonTreeViewerCss = "jsontreeviewer/jsonTree.css";
      let jsonTreeViewerCssUri = qx.util.ResourceManager.getInstance().toUri(jsonTreeViewerCss);
      qx.module.Css.includeStylesheet(jsonTreeViewerCssUri);
      let dynLoader = new qx.util.DynamicScriptLoader([
        jsonTreeViewerPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(jsonTreeViewerPath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    print: function(data, wrapper) {
      jsonTree.create(data, wrapper);
      // tree.expand();
    }
  }
});
