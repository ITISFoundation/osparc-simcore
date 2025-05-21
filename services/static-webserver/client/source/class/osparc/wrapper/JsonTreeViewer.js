/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global jsonTree */

/**
 * @asset(jsontreeviewer/jsonTree.*)
 * @asset(jsontreeviewer/icons.svg)
 * @ignore(jsonTree)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/summerstyle/jsonTreeViewer' target='_blank'>JsonTreeViewer</a>
 */

qx.Class.define("osparc.wrapper.JsonTreeViewer", {
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
      const jsonTreeViewerPath = "jsontreeviewer/jsonTree.js";
      const jsonTreeViewerCss = "jsontreeviewer/jsonTree.css";
      const jsonTreeViewerCssUri = qx.util.ResourceManager.getInstance().toUri(jsonTreeViewerCss);
      qx.module.Css.includeStylesheet(jsonTreeViewerCssUri);
      const dynLoader = new qx.util.DynamicScriptLoader([
        jsonTreeViewerPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(jsonTreeViewerPath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        const data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    print: function(jsonObj, domEl) {
      const tree = jsonTree.create(jsonObj, domEl);
      tree.expand();
    }
  }
});
