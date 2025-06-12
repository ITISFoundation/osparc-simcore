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
            const beUiConfig = values[0];
            const feUiConfig = values[1];
            const schema = values[2];
            if (beUiConfig && beUiConfig["ui"] && Object.keys(beUiConfig["ui"]).length) {
              uiConfig = beUiConfig["ui"];
            } else {
              const product = osparc.product.Utils.getProductName();
              if (feUiConfig && product in feUiConfig) {
                uiConfig = feUiConfig[product];
              }
            }
            const ajvLoader = new qx.util.DynamicScriptLoader([
              "/resource/ajv/ajv-6-11-0.min.js",
              "/resource/object-path/object-path-0-11-4.min.js"
            ]);
            ajvLoader.addListener("ready", () => {
              const ajv = new Ajv({
                allErrors: true,
                strictDefaults: true,
                useDefaults: true,
                strictTypes: true,
              });
              const validate = ajv.compile(schema);
              const valid = validate(uiConfig);
              if (valid) {
                this.__uiConfig = uiConfig;
                resolve(this.__uiConfig);
              } else {
                osparc.FlashMessenger.logError("Wrong product.ui config");
                validate.errors.forEach(err => {
                  console.error(`Error at ${err.dataPath}: ${err.message}`);
                });
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

    getGroupedServicesUiConfig: function() {
      return this.__uiConfig["groupedServices"];
    },
  }
});
