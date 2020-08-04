/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Security page
 *
 *  - access token
 *  - reset password (logged in)
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.SecurityPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/shield-alt/24";
    const title = this.tr("Security");
    this.base(arguments, title, iconSrc);

    this.add(this.__createPasswordSection());

    this.add(this.__createAPIKeysSection());
    this.add(this.__createTokensSection());

    this.__rebuildAPIKeysList();
    this.__rebuildTokensList();
  },

  members: {
    __apiKeysList: null,
    __tokensList: null,
    __requestAPIKeyBtn: null,

    __createPasswordSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("Password"));

      const currentPassword = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your current password")
      });
      box.add(currentPassword);

      const newPassword = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your new password")
      });
      box.add(newPassword);

      const confirm = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype your new password")
      });
      box.add(confirm);

      const manager = new qx.ui.form.validation.Manager();
      manager.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(newPassword, confirm);
      });

      const resetBtn = new qx.ui.form.Button("Reset Password").set({
        allowGrowX: false
      });
      box.add(resetBtn);

      resetBtn.addListener("execute", () => {
        if (manager.validate()) {
          const params = {
            data: {
              current: currentPassword.getValue(),
              new: newPassword.getValue(),
              confirm: confirm.getValue()
            }
          };
          osparc.data.Resources.fetch("password", "post", params)
            .then(data => {
              osparc.component.message.FlashMessenger.getInstance().log(data);
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            })
            .catch(err => {
              console.error(err);
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed to reset password"), "ERROR");
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            });
        }
      });

      return box;
    },

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
        .then(apiKeysList => {
          if (apiKeysList.length) {
            for (let i = 0; i < apiKeysList.length; i++) {
              const apiKeyForm = this.__createValidAPIKeyForm(apiKeysList[i]);
              this.__apiKeysList.add(apiKeyForm);
            }
          }
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
        column: 2
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

    __createTokensSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("External Service Tokens"));

      const label = this._createHelpLabel(this.tr(
        "List of API tokens to access external services. Currently, \
         only DAT-Core API keys are supported."
      ));
      box.add(label);

      const linkBtn = new osparc.ui.form.LinkButton(this.tr("To DAT-Core"), "https://app.blackfynn.io");
      box.add(linkBtn);

      const tokensList = this.__tokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(tokensList);

      return box;
    },

    __rebuildTokensList: function() {
      this.__tokensList.removeAll();
      osparc.data.Resources.get("tokens")
        .then(tokensList => {
          if (tokensList.length) {
            for (let i = 0; i < tokensList.length; i++) {
              const tokenForm = this.__createValidTokenForm(tokensList[i]);
              this.__tokensList.add(tokenForm);
            }
          } else {
            const emptyForm = this.__createEmptyTokenForm();
            this.__tokensList.add(new qx.ui.form.renderer.Single(emptyForm));
          }
        })
        .catch(err => console.error(err));
    },

    __createEmptyTokenForm: function() {
      const form = new qx.ui.form.Form();

      // FIXME: for the moment this is fixed since it has to be a unique id
      const newTokenService = new qx.ui.form.TextField();
      newTokenService.set({
        value: "blackfynn-datcore",
        readOnly: true
      });
      form.add(newTokenService, this.tr("Service"));

      const newTokenKey = new qx.ui.form.TextField();
      newTokenKey.set({
        placeholder: this.tr("Introduce token key here")
      });
      form.add(newTokenKey, this.tr("Key"));

      const newTokenSecret = new qx.ui.form.TextField();
      newTokenSecret.set({
        placeholder: this.tr("Introduce token secret here")
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
        column: 3
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
      gr.setColumnFlex(1, 1);
      gr.setRowHeight(0, height);
      gr.setRowHeight(1, height);
      gr.setRowHeight(2, height);
      const grid = new qx.ui.container.Composite(gr);
      return grid;
    }
  }
});
