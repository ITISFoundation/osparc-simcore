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
    this.add(this.__createInternalTokensSection());
    this.add(this.__createExternalTokensSection());

    this.__rebuildTokensList();
  },

  members: {
    __internalTokensList: null,
    __externalTokensList: null,

    __createInternalTokensSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("oSPARC API Tokens"));

      const label = this._createHelpLabel(this.tr(
        "Tokens to access oSPARC API."
      ));
      box.add(label);

      const tokensList = this.__internalTokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(tokensList);

      const requestTokenBtn = this.__requestTokenBtn = new osparc.ui.form.FetchButton(this.tr("Create oSPARC Token")).set({
        allowGrowX: false
      });
      requestTokenBtn.addListener("execute", () => {
        this.__requestOsparcToken();
      }, this);
      box.add(requestTokenBtn);

      return box;
    },

    __requestOsparcToken: function() {
      if (!osparc.data.Permissions.getInstance().canDo("preferences.token.create", true)) {
        return;
      }

      const createAPIKeyWindow = new osparc.desktop.preferences.window.CreateAPIKey("hello", "world");
      createAPIKeyWindow.addListener("finished", keyLabel => {
        const params = {
          data: {
            "service": "osparc",
            "keyLabel": keyLabel.getData()
          }
        };
        createAPIKeyWindow.close();
        this.__requestTokenBtn.setFetching(true);
        osparc.data.Resources.fetch("tokens", "post", params)
          .then(data => {
            this.__rebuildTokensList();
            const showAPIKeyWindow = new osparc.desktop.preferences.window.ShowAPIKey("hello", "world");
            showAPIKeyWindow.center();
            showAPIKeyWindow.open();
            console.log(data);
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed creating oSPARC API token"), "ERROR");
            console.error(err);
          })
          .finally(() => this.__requestTokenBtn.setFetching(false));
      }, this);
      createAPIKeyWindow.open();
    },

    __createExternalTokensSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("External service Tokens"));

      const label = this._createHelpLabel(this.tr(
        "List of API tokens to access external services. Currently, \
         only DAT-Core API keys are supported."
      ));
      box.add(label);

      const linkBtn = new osparc.ui.form.LinkButton(this.tr("To DAT-Core"), "https://app.blackfynn.io");
      box.add(linkBtn);

      const tokensList = this.__externalTokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(tokensList);

      return box;
    },

    __rebuildTokensList: function() {
      this.__internalTokensList.removeAll();
      this.__externalTokensList.removeAll();
      osparc.data.Resources.get("tokens")
        .then(tokensList => {
          if (tokensList.length) {
            for (let i = 0; i < tokensList.length; i++) {
              const tokenForm = this.__createValidTokenForm(tokensList[i]);
              if (tokensList[i].service === "osparc") {
                this.__internalTokensList.add(tokenForm);
              } else {
                this.__externalTokensList.add(tokenForm);
              }
            }
          } else {
            const emptyForm = this.__createEmptyTokenForm();
            this.__externalTokensList.add(new qx.ui.form.renderer.Single(emptyForm));
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
        if (!osparc.data.Permissions.getInstance().canDo("preferences.token.create", true)) {
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
      const label = token["keyLabel"] || token["service"];
      const service = token["service"];

      const height = 20;
      const iconHeight = height - 6;
      const gr = new qx.ui.layout.Grid(10, 3);
      gr.setColumnFlex(1, 1);
      gr.setRowHeight(0, height);
      gr.setRowHeight(1, height);
      gr.setRowHeight(2, height);
      const grid = new qx.ui.container.Composite(gr);

      const nameLabel = new qx.ui.basic.Label(service);
      grid.add(nameLabel, {
        row: 0,
        column: 0
      });

      const nameVal = new qx.ui.basic.Label(label);
      grid.add(nameVal, {
        row: 0,
        column: 1
      });

      const delTokenBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/trash-alt/" + iconHeight);
      delTokenBtn.addListener("execute", e => {
        if (!osparc.data.Permissions.getInstance().canDo("preferences.token.delete", true)) {
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
      }, this);
      grid.add(delTokenBtn, {
        row: 0,
        column: 3
      });

      return grid;
    },

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
    }
  }
});
