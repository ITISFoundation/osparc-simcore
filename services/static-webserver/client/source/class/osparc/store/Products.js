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
          this.__getUIConfig(),
          osparc.utils.Utils.fetchJSON("/resource/schemas/product-ui.json"),
        ])
          .then(values => {
            const uiConfig = values[0];
            const schema = values[1];
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

    __getUIConfig: function() {
      return Promise.all([
        this.__getUiConfigBackend(),
        this.__getUiConfigFrontend(),
      ])
        .then(values => {
          const beUiConfig = values[0];
          if (beUiConfig) {
            return beUiConfig;
          }
          const feUiConfig = values[1];
          return feUiConfig || {};
        });
    },

    __getUiConfigBackend: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        // Guest users do not have access to product metadata
        return Promise.resolve(null);
      }
      return osparc.data.Resources.fetch("productMetadata", "getUiConfig")
        .then(response => {
          if (response && response["ui"] && Object.keys(response["ui"]).length) {
            return response["ui"];
          }
          return null;
        });
    },

    __getUiConfigFrontend: function() {
      return osparc.utils.Utils.fetchJSON("/resource/osparc/ui_config.json")
        .then(uiConfig => {
          const product = osparc.product.Utils.getProductName();
          if (uiConfig && product in uiConfig) {
            return uiConfig[product];
          }
          return null;
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

    getSupportGroupId: function() {
      return 23;
    },

    amIASupportUser: function() {
      const supportGroupId = this.getSupportGroupId();
      const groupsStore = osparc.store.Groups.getInstance();
      const myGroupIds = groupsStore.getOrganizationIds().map(gId => parseInt(gId));
      return (supportGroupId && myGroupIds.includes(supportGroupId));
    },
  }
});
