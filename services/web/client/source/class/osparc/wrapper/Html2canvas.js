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
    VERSION: "1.4.1",
    URL: "https://github.com/niklasvh/html2canvas"
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
      return new Promise((resolve, reject) => {
        const bgColor = qx.theme.manager.Color.getInstance().resolve("background-main");
        html2canvas(element, {
          allowTaint: true,
          useCORS: true,
          backgroundColor: bgColor,
          width: 1440,
          height: 900
        })
          .then(canvas => {
            const image = canvas.toDataURL("image/png");
            resolve(image);
          })
          .catch(err => reject(err));
      });
    }
  }
});
