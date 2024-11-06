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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this._add(this.__createAPIKeysSection());
    this._add(this.__createTokensSection());

    this.__rebuildAPIKeysList();
    this.__rebuildTokensList();
  },

  members: {
    __apiKeysList: null,
    __validTokensGB: null,
    __supportedExternalsGB: null,
    __requestAPIKeyBtn: null,

    __createAPIKeysSection: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("API Keys"));

      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr(
        "List API keys associated to your account."
      ));
      box.add(label);

      const apiKeysList = this.__apiKeysList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(apiKeysList);

      const requestAPIKeyBtn = this.__requestAPIKeyBtn = new osparc.ui.form.FetchButton().set({
        appearance: "strong-button",
        label: this.tr("New API Key"),
        icon: "@FontAwesome5Solid/plus/14",
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
      createAPIKeyWindow.addListener("finished", e => {
        const formData = e.getData();
        const params = {
          data: {
            "display_name": formData["name"]
          }
        };
        if (formData["expiration"]) {
          const seconds = parseInt((new Date(formData["expiration"]).getTime() - new Date().getTime()) / 1000);
          params.data["expiration"] = seconds
        }
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
            osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          })
          .finally(() => this.__requestAPIKeyBtn.setFetching(false));
      }, this);
      createAPIKeyWindow.open();
    },

    __rebuildAPIKeysList: function() {
      this.__apiKeysList.removeAll();
      osparc.data.Resources.get("apiKeys")
        .then(apiKeys => {
          apiKeys.forEach(apiKey => {
            const apiKeyForm = this.__createValidAPIKeyForm(apiKey);
            this.__apiKeysList.add(apiKeyForm);
          });
        })
        .catch(err => console.error(err));
    },

    __createValidAPIKeyForm: function(apiKeyLabel) {
      const grid = this.__createValidEntryLayout();

      const nameLabel = new qx.ui.basic.Label(apiKeyLabel);
      grid.add(nameLabel, {
        row: 0,
        column: 0
      });

      const delAPIKeyBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/trash/14");
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

      const msg = this.tr("Do you want to delete the API key?");
      const win = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete API key"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const params = {
            data: {
              "display_name": apiKeyLabel
            }
          };
          osparc.data.Resources.fetch("apiKeys", "delete", params)
            .then(() => this.__rebuildAPIKeysList())
            .catch(err => console.error(err));
        }
      }, this);
    },

    __supportedExternalServices: function() {
      const supportedServices = [{
        name: "pennsieve-datcore",
        label: "DAT-Core",
        link: "https://app.pennsieve.io",
        logo: "osparc/blackfynn-logo.png"
      }];
      return supportedServices;
    },

    __createTokensSection: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("External Service Tokens"));

      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr("Enter the API tokens to access external services."));
      box.add(label);

      const validTokensGB = this.__validTokensGB = osparc.ui.window.TabbedView.createSectionBox(this.tr("Existing Tokens"));
      box.add(validTokensGB);

      const supportedExternalsGB = this.__supportedExternalsGB = osparc.ui.window.TabbedView.createSectionBox(this.tr("Supported services")).set({
        layout: new qx.ui.layout.Flow(5, 5)
      });
      box.add(supportedExternalsGB);

      return box;
    },

    __rebuildTokensList: function() {
      this.__validTokensGB.exclude();
      this.__supportedExternalsGB.exclude();
      osparc.data.Resources.get("tokens")
        .then(tokensList => {
          this.__validTokensGB.removeAll();
          this.__supportedExternalsGB.removeAll();

          const supportedExternalServices = osparc.utils.Utils.deepCloneObject(this.__supportedExternalServices());

          tokensList.forEach(token => {
            const tokenForm = this.__createValidTokenEntry(token);
            this.__validTokensGB.add(tokenForm);
            const idx = supportedExternalServices.findIndex(srv => srv.name === token.service);
            if (idx > -1) {
              supportedExternalServices.splice(idx, 1);
            }
          });

          supportedExternalServices.forEach(srv => {
            const btn = new qx.ui.form.Button(srv.label, srv.logo).set({
              iconPosition: "top",
              width: 80,
              height: 80
            });
            btn.getChildControl("icon").set({
              scale: true,
              maxWidth: 50,
              maxHeight: 50
            });
            btn.addListener("execute", () => {
              const newTokenForm = this.__createNewTokenForm(srv);
              const form = new qx.ui.form.renderer.Single(newTokenForm);
              const win = osparc.ui.window.Window.popUpInWindow(form, srv.label, 350, 200);
              newTokenForm.addListener("added", () => {
                this.__rebuildTokensList();
                win.close();
              });
            }, this);
            this.__supportedExternalsGB.add(btn);
          });

          if (tokensList.length) {
            this.__validTokensGB.show();
          }
          if (supportedExternalServices.length) {
            this.__supportedExternalsGB.show();
          }
        })
        .catch(err => console.error(err));
    },

    __createValidTokenEntry: function(token) {
      const grid = this.__createValidEntryLayout();

      const service = token["service"];
      const nameLabel = new qx.ui.basic.Label(service);
      grid.add(nameLabel, {
        row: 0,
        column: 0
      });

      if ("keyLabel" in token) {
        const label = token["keyLabel"];
        const nameVal = new qx.ui.basic.Label(label);
        grid.add(nameVal, {
          row: 0,
          column: 1
        });
      }

      const delTokenBtn = new qx.ui.form.Button().set({
        appearance: "danger-button",
        icon: "@FontAwesome5Solid/trash/14"
      });
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

      const msg = this.tr("Do you want to delete the Token?");
      const win = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete Token"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const params = {
            url: {
              service
            }
          };
          osparc.data.Resources.fetch("tokens", "delete", params)
            .then(() => this.__rebuildTokensList())
            .catch(err => console.error(err));
        }
      }, this);
    },

    __createValidEntryLayout: function() {
      const height = 20;
      const gr = new qx.ui.layout.Grid(10, 3);
      gr.setColumnFlex(0, 1);
      gr.setRowHeight(0, height); // Link
      gr.setRowHeight(1, height); // Token entry
      const grid = new qx.ui.container.Composite(gr);
      return grid;
    },

    __createNewTokenForm: function(supportedExternalServices) {
      const form = new qx.ui.form.Form();

      form.addGroupHeader("Add new service API tokens");

      const newTokenService = new qx.ui.form.TextField();
      newTokenService.set({
        value: supportedExternalServices["name"],
        readOnly: true
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

      const addTokenBtn = new osparc.ui.form.FetchButton(this.tr("Add"));
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
        addTokenBtn.setFetching(true);
        osparc.data.Resources.fetch("tokens", "post", params)
          .then(() => form.fireEvent("added"))
          .catch(err => console.error(err))
          .finally(() => addTokenBtn.setFetching(false));
      }, this);
      form.addButton(addTokenBtn);

      return form;
    }
  }
});
