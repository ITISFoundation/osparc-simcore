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
  extend:osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/shield-alt/24";
    const title = this.tr("Security");
    this.base(arguments, title, iconSrc);

    this.add(this.__createPasswordSection());
    this.add(this.__createTokensSection());
  },

  members: {
    __tokensList: null,

    __createTokensSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("Access Tokens"));

      const label = this._createHelpLabel(this.tr(
        "List of API tokens to access external services. Currently, \
         only DAT-Core API keys are supported."
      ));
      box.add(label);

      let linkBtn = new osparc.ui.form.LinkButton(this.tr("To DAT-Core"), "https://app.blackfynn.io");
      box.add(linkBtn);

      const tokensList = this.__tokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      box.add(tokensList);
      this.__rebuildTokensList();

      return box;
    },

    __rebuildTokensList: function() {
      this.__tokensList.removeAll();
      osparc.data.Resources.get("tokens")
        .then(tokensList => {
          if (tokensList.length) {
            for (let i=0; i<tokensList.length; i++) {
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
      let form = new qx.ui.form.Form();

      // FIXME: for the moment this is fixed since it has to be a unique id
      let newTokenService = new qx.ui.form.TextField();
      newTokenService.set({
        value: "blackfynn-datcore",
        readOnly: true
      });
      form.add(newTokenService, this.tr("Service"));

      // TODO:
      let newTokenKey = new qx.ui.form.TextField();
      newTokenKey.set({
        placeholder: this.tr("Introduce token key here")
      });
      form.add(newTokenKey, this.tr("Key"));

      let newTokenSecret = new qx.ui.form.TextField();
      newTokenSecret.set({
        placeholder: this.tr("Introduce token secret here")
      });
      form.add(newTokenSecret, this.tr("Secret"));

      let addTokenBtn = new qx.ui.form.Button(this.tr("Add"));
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
      const service = token["service"];

      const height = 20;
      const iconHeight = height-6;
      const gr = new qx.ui.layout.Grid(10, 3);
      gr.setColumnFlex(1, 1);
      gr.setRowHeight(0, height);
      gr.setRowHeight(1, height);
      gr.setRowHeight(2, height);
      const grid = new qx.ui.container.Composite(gr);

      const nameLabel = new qx.ui.basic.Label(this.tr("Token name"));
      grid.add(nameLabel, {
        row: 0,
        column: 0
      });

      const nameVal = new qx.ui.basic.Label(service);
      grid.add(nameVal, {
        row: 0,
        column: 1
      });

      /*
      const showTokenIcon = "@FontAwesome5Solid/edit/"+iconHeight;
      const showTokenBtn = new qx.ui.form.Button(null, showTokenIcon);
      showTokenBtn.addListener("execute", e => {
        const treeItemRenamer = new osparc.component.widget.Renamer(nameVal.getValue());
        treeItemRenamer.addListener("labelChanged", ev => {
          const newLabel = ev.getData()["newLabel"];
          nameVal.setValue(newLabel);
        }, this);
        treeItemRenamer.center();
        treeItemRenamer.open();
      }, this);
      grid.add(showTokenBtn, {
        row: 0,
        column: 2
      });
      */

      const delTokenBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/trash-alt/"+iconHeight);
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
      let box = this._createSectionBox(this.tr("Password"));

      let currentPassword = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your current password")
      });
      box.add(currentPassword);

      let newPassword = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your new password")
      });
      box.add(newPassword);

      let confirm = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype your new password")
      });
      box.add(confirm);

      let manager = new qx.ui.form.validation.Manager();
      manager.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(newPassword, confirm);
      });

      let resetBtn = new qx.ui.form.Button("Reset Password").set({
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
