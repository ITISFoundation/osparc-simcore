/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(jsonFormatter/json-formatter-2.5.23.js)
 * @asset(jsonFormatter/json-formatter-2.5.23.css)
 * @ignore(JSONFormatter)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://azimi.me/json-formatter-js/' target='_blank'>JSONFormatter</a>
 */

qx.Class.define("osparc.wrapper.JsonFormatter", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  statics: {
    NAME: "JSONFormatter",
    VERSION: "2.5.23",
    URL: "https://azimi.me/json-formatter-js/",
  },

  members: {
    init: function() {
      return new Promise((resolve, reject) => {
        if (this.getLibReady()) {
          resolve();
          return;
        }

        const jsonFormatterCss = "jsonFormatter/json-formatter-2.5.23.css";
        const jsonFormatterCssUri = qx.util.ResourceManager.getInstance().toUri(jsonFormatterCss);
        qx.module.Css.includeStylesheet(jsonFormatterCssUri);

        // initialize the script loading
        const jsonFormatterPath = "jsonFormatter/json-formatter-2.5.23.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          jsonFormatterPath
        ]);

        dynLoader.addListenerOnce("ready", () => {
          console.log(jsonFormatterPath + " loaded");
          this.setLibReady(true);
          resolve();
        }, this);

        dynLoader.addListener("failed", e => {
          const data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    setData: function(myJSON) {
      const formatter = new JSONFormatter(myJSON);
      document.body.appendChild(formatter.render());
    },
  }
});
