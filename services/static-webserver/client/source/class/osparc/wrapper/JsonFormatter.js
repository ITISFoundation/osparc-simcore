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

    createContainer: function(divId) {
      const container = new qx.ui.embed.Html("<div id='"+divId+"'></div>");

      // Inject custom CSS for the JSONFormatter container
      const styleId = "json-formatter-custom-style";
      if (!document.getElementById(styleId)) {
        const color = qx.theme.manager.Color.getInstance().resolve("text");
        const style = document.createElement("style");
        style.id = styleId;
        style.innerHTML = `
          #${divId} * {
            color: ${color} !important; /* Use osparc text color */
            font-family: "Manrope", sans-serif !important; /* Use osparc font */
          }
          #${divId} .json-formatter-key {
            font-size: 13px !important; /* Actually keeping the default size */
          }
          #${divId} .json-formatter-constructor-name {
            display: none !important; /* Hide "Object" and "Array(n)" labels */
          }
        `;
        document.head.appendChild(style);
      }

      return container
    },

    setJson: function(jsonObject, divId) {
      // Remove previous content
      const container = document.getElementById(divId);
      container.innerHTML = "";

      // Render JSON
      const formatter = new JSONFormatter(jsonObject, 2); // 2 = expand depth
      container.appendChild(formatter.render());
    },
  }
});
