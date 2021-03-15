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

/**
 *  Tokens page
 *  - access token
 */

qx.Class.define("osparc.desktop.preferences.pages.TokensPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/shield-alt/24";
    const title = this.tr("API");
    this.base(arguments, title, iconSrc);

    this.add(this.__createAPIKeysSection());
    this.add(this.__createTokensSection());

    this.__rebuildAPIKeysList();
    this.__rebuildTokensList();
  },

  members: {
    __apiKeysList: null,
    __tokensList: null,
    __requestAPIKeyBtn: null,

    __createAPIKeysSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("API Keys"));

      const label = this._createHelpLabel(this.tr(
        "List API keys associated to your account."
      ));
      box.add(label);

      const apiKeysList = this.__apiKeysList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(apiKeysList);

      const requestAPIKeyBtn = this.__requestAPIKeyBtn = new osparc.ui.form.FetchButton(this.tr("Create API Key")).set({
        allowGrowX: false
      });
      requestAPIKeyBtn.addListener("execute", () => {
        this.__requestAPIKey();
      }, this);
      box.add(requestAPIKeyBtn);

      return box;
    },

    __requestAPIKey: function() {
      if (!osparc.data.Permissions.getInstance().canDo("user.apikey.create", true)) {
        return;
      }

      const createAPIKeyWindow = new osparc.desktop.preferences.window.CreateAPIKey();
      createAPIKeyWindow.addListener("finished", keyLabel => {
        const params = {
          data: {
            "display_name": keyLabel.getData()
          }
        };
        createAPIKeyWindow.close();
        this.__requestAPIKeyBtn.setFetching(true);
        osparc.data.Resources.fetch("apiKeys", "post", params)
          .then(data => {
            this.__rebuildAPIKeysList();

            const key = data["api_key"];
            const secret = data["api_secret"];
            const showAPIKeyWindow = new osparc.desktop.preferences.window.ShowAPIKey(key, secret);
            showAPIKeyWindow.center();
            showAPIKeyWindow.open();
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          })
          .finally(() => this.__requestAPIKeyBtn.setFetching(false));
      }, this);
      createAPIKeyWindow.open();
    },

    __rebuildAPIKeysList: function() {
      this.__apiKeysList.removeAll();
      osparc.data.Resources.get("apiKeys")
        .then(apiKeys => {
          console.log("apiKeys", apiKeys);
          apiKeys.forEach(apiKey => {
            const apiKeyForm = this.__createValidAPIKeyForm(apiKey);
            this.__apiKeysList.add(apiKeyForm);
          });
        })
        .catch(err => console.error(err));
    },

    __createValidAPIKeyForm: function(apiKeyLabel) {
      const grid = this.__createValidEntryForm();

      const nameLabel = new qx.ui.basic.Label(apiKeyLabel);
      grid.add(nameLabel, {
        row: 0,
        column: 0
      });

      const delAPIKeyBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/trash-alt/14");
      delAPIKeyBtn.addListener("execute", e => {
        this.__deleteAPIKey(apiKeyLabel);
      }, this);
      grid.add(delAPIKeyBtn, {
        row: 0,
        column: 1
      });

      return grid;
    },

    __deleteAPIKey: function(apiKeyLabel) {
      if (!osparc.data.Permissions.getInstance().canDo("user.apikey.delete", true)) {
        return;
      }
      const params = {
        data: {
          "display_name": apiKeyLabel
        }
      };
      osparc.data.Resources.fetch("apiKeys", "delete", params)
        .then(() => this.__rebuildAPIKeysList())
        .catch(err => console.error(err));
    },

    __supportedServices: function() {
      const supportedServices = [{
        name: "blackfynn-datcore",
        label: "DAT-Core",
        link: "https://app.blackfynn.io",
        logo: "blackfynn-logo.png"
      }];
      if (osparc.utils.Utils.isInZ43()) {
        supportedServices.push({
          name: "z43-filesrv",
          label: "z43-filesrv",
          link: "https://www.z43.swiss/",
          logo: "z43-logo.png"
        });
      }
      return supportedServices;
    },

    __createTokensSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("External Service Tokens"));

      const label = this._createHelpLabel(this.tr("List of API tokens to access external services. Supported services:"));
      this.__supportedServices().forEach(supportedService => {
        label.setValue(`${label.getValue()} <br>- ${supportedService["label"]} (${supportedService["name"]})`);
      });
      box.add(label);

      const tokensList = this.__tokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(tokensList);

      return box;
    },

    __rebuildTokensList: function() {
      this.__tokensList.removeAll();
      osparc.data.Resources.get("tokens")
        .then(tokensList => {
          console.log("tokens", tokensList);
          tokensList.forEach(token => {
            const tokenForm = this.__createValidTokenForm(token);
            this.__tokensList.add(tokenForm);
          });

          const emptyForm = this.__createEmptyTokenForm();
          this.__tokensList.add(new qx.ui.form.renderer.Single(emptyForm));
        })
        .catch(err => console.error(err));
    },

    __createEmptyTokenForm: function() {
      const form = new qx.ui.form.Form();

      form.addGroupHeader("Add new service API tokens");

      // FIXME: for the moment this is fixed since it has to be a unique id
      const newTokenService = new qx.ui.form.TextField();
      newTokenService.set({
        placeholder: this.tr("Input unique service name, i.e. ") + this.__supportedServices()[0]["name"]
      });
      form.add(newTokenService, this.tr("Service"));

      const newTokenKey = new qx.ui.form.TextField();
      newTokenKey.set({
        placeholder: this.tr("Input your token key")
      });
      form.add(newTokenKey, this.tr("Key"));

      const newTokenSecret = new qx.ui.form.TextField();
      newTokenSecret.set({
        placeholder: this.tr("Input your token secret")
      });
      form.add(newTokenSecret, this.tr("Secret"));

      const addTokenBtn = new qx.ui.form.Button(this.tr("Add"));
      addTokenBtn.setWidth(100);
      addTokenBtn.addListener("execute", e => {
        if (!osparc.data.Permissions.getInstance().canDo("user.token.create", true)) {
          return;
        }
        const params = {
          data: {
            "service": newTokenService.getValue(),
            "token_key": newTokenKey.getValue(),
            "token_secret": newTokenSecret.getValue()
          }
        };
        osparc.data.Resources.fetch("tokens", "post", params)
          .then(() => this.__rebuildTokensList())
          .catch(err => console.error(err));
      }, this);
      form.addButton(addTokenBtn);

      return form;
    },

    __createValidTokenForm: function(token) {
      const grid = this.__createValidEntryForm();

      const supportedServices = this.__supportedServices();

      const service = token["service"];
      const nameLabel = new qx.ui.basic.Label(service);
      grid.add(nameLabel, {
        row: 0,
        column: 0
      });

      const label = token["keyLabel"] || token["service"];
      const nameVal = new qx.ui.basic.Label(label);
      grid.add(nameVal, {
        row: 0,
        column: 1
      });

      const delTokenBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/trash-alt/14");
      delTokenBtn.addListener("execute", e => {
        this.__deleteToken(service);
      }, this);
      grid.add(delTokenBtn, {
        row: 0,
        column: 2
      });

      return grid;
    },

    __deleteToken: function(service) {
      if (!osparc.data.Permissions.getInstance().canDo("user.token.delete", true)) {
        return;
      }
      const params = {
        url: {
          service
        }
      };
      osparc.data.Resources.fetch("tokens", "delete", params, service)
        .then(() => this.__rebuildTokensList())
        .catch(err => console.error(err));
    },

    __createValidEntryForm: function() {
      const height = 20;
      const gr = new qx.ui.layout.Grid(10, 3);
      gr.setColumnFlex(0, 1);
      gr.setRowHeight(0, height); // Link
      gr.setRowHeight(1, height); // Token entry
      const grid = new qx.ui.container.Composite(gr);
      return grid;
    }
  }
});
