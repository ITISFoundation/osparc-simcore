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

/**
 * @asset(jszip/jszip.min.js)
 * @ignore(JSZip)
 */

/* global JSZip */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/Stuk/jszip' target='_blank'>JSZip</a>
 */

qx.Class.define("osparc.wrapper.JsZip", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "JSZip",
    VERSION: "3.2.2",
    URL: "https://github.com/Stuk/jszip"
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
      const jsZipPath = "jszip/jszip.min.js";
      const dynLoader = new qx.util.DynamicScriptLoader([
        jsZipPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(jsZipPath + " loaded");

        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    zipFiles: function(files) {
      const zip = new JSZip();
      for (let i=0; i<files.length; i++) {
        const fileName = files[i].name;
        const fileContent = files[i].content;
        zip.file(fileName, fileContent);
      }
      const content = zip.generateAsync({
        type: "nodebuffer",
        mimeType: "application/epub+zip"
      });
      return content;
    }
  }
});
