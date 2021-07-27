/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global html2canvas */

/**
 * @asset(html2canvas/html2canvas.min.js)
 * @ignore(html2canvas)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/niklasvh/html2canvas' target='_blank'>Html2canvas</a>
 */

qx.Class.define("osparc.wrapper.Html2canvas", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "html2canvas",
    VERSION: "1.1.4",
    URL: "https://github.com/niklasvh/html2canvas"
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
      const html2canvasPath = "html2canvas/html2canvas.min.js";
      const dynLoader = new qx.util.DynamicScriptLoader([
        html2canvasPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(html2canvasPath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        const data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    takeScreenshot: function(element) {
      const bgColor = qx.theme.manager.Color.getInstance().resolve("background-main");
      html2canvas(element, {
        allowTaint: true,
        useCORS: true,
        backgroundColor: bgColor
      })
        .then(canvas => {
          const quality = 0.9;
          const image = canvas.toDataURL("image/png", quality);
          const a = document.createElement("a");
          a.href = image;
          a.download = "somefilename.jpg";
          a.click();
        });
    }
  }
});
