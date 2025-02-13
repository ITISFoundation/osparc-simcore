/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(osparc/ui_config.json")
 * @asset(schemas/product-ui.json)
 * @asset(object-path/object-path-0-11-4.min.js)
 * @asset(ajv/ajv-6-11-0.min.js)
 * @ignore(Ajv)
 */

qx.Class.define("osparc.store.Products", {
  extend: qx.core.Object,
  type: "singleton",

  members: {
    __uiConfig: null,

    fetchUiConfig: function() {
      return new Promise(resolve => {
        if (osparc.auth.Data.getInstance().isGuest()) {
          this.__uiConfig = {};
          resolve(this.__uiConfig);
        }

        Promise.all([
          osparc.data.Resources.fetch("productMetadata", "getUiConfig"),
          osparc.utils.Utils.fetchJSON("/resource/osparc/ui_config.json"),
          osparc.utils.Utils.fetchJSON("/resource/schemas/product-ui.json"),
        ])
          .then(values => {
            let uiConfig = {};
            if (values[0] && values[0]["ui"] && Object.keys(values[0]["ui"]).length) {
              uiConfig = values[0]["ui"];
            } else {
              const product = osparc.product.Utils.getProductName();
              if (values[1] && product in values[1]) {
                uiConfig = values[1][product];
              }
            }
            // const schema = values[2];
            const schema = {
              "type": "object",
              "properties": {
                "resourceType": { "type": "string" },
                "title": { "type": "string" },
                "icon": { "type": "string" },
                "newStudyLabel": { "type": "string" },
                "idToWidget": { "type": "string" }
              },
              "required": ["resourceType", "title"],
            };
            const ajvLoader = new qx.util.DynamicScriptLoader([
              "/resource/ajv/ajv-6-11-0.min.js",
              "/resource/object-path/object-path-0-11-4.min.js"
            ]);
            ajvLoader.addListener("ready", () => {
              const ajv = new Ajv({
                allErrors: true,
                strictDefaults: true,
                useDefaults: true,
              });
              const validate = ajv.compile(schema);
              const valid = validate(uiConfig);
              if (valid) {
                // Validate data if present
                this.__uiConfig = uiConfig;
                resolve(this.__uiConfig);
              } else {
                console.error("wrong ui_config")
              }
            });
            ajvLoader.addListener("failed", console.error, this);
            ajvLoader.start();
          })
          .catch(console.error);
      });
    },

    getPlusButtonUiConfig: function() {
      return this.__uiConfig["plusButton"];
    },

    getNewStudiesUiConfig: function() {
      return this.__uiConfig["newStudies"];
    },
  }
});
