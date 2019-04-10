/* ************************************************************************

   qxapp - the simcore frontend

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

qx.Class.define("qxapp.desktop.preferences.pages.SecurityPage", {
  extend:qxapp.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/shield-alt/24";
    const title = this.tr("Security");
    this.base(arguments, title, iconSrc);

    this.__tokenResources = qxapp.io.rest.ResourceFactory.getInstance().createTokenResources();

    this.add(this.__createPasswordSection());
    this.add(this.__createTokensSection());
  },

  members: {
    __tokenResources: null,

    __tokensList: null,

    __createTokensSection: function() {
      // layout
      let box = this._createSectionBox(this.tr("Access Tokens"));

      let label = this._createHelpLabel(this.tr(
        "List of API tokens to access external services. Currently, \
         only DAT-Core API keys are supported."
      ));
      box.add(label);

      let linkBtn = new qxapp.component.widget.LinkButton(this.tr("To DAT-Core"), "https://app.blackfynn.io");
      box.add(linkBtn);

      this.__tokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this.__rebuildTokensList();
      box.add(this.__tokensList);

      return box;
    },

    __rebuildTokensList: function() {
      this.__tokensList.removeAll();

      let tokens = this.__tokenResources.tokens;
      tokens.addListenerOnce("getSuccess", e => {
        let tokensList = e.getRequest().getResponse().data;
        if (tokensList.length === 0) {
          let emptyForm = this.__createEmptyTokenForm();
          this.__tokensList.add(new qx.ui.form.renderer.Single(emptyForm));
        } else {
          for (let i=0; i<tokensList.length; i++) {
            const token = tokensList[i];
            let tokenForm = this.__createValidTokenForm(token["service"], token["token_key"], token["token_secret"]);
            this.__tokensList.add(new qx.ui.form.renderer.Single(tokenForm));
          }
        }
      }, this);

      tokens.addListenerOnce("getError", e => {
        console.error(e);
      });
      tokens.get();
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
        let tokens = this.__tokenResources.tokens;
        tokens.addListenerOnce("postSuccess", ev => {
          this.__rebuildTokensList();
        }, this);
        tokens.addListenerOnce("getError", ev => {
          console.error(ev);
        });
        const newTokenInfo = {
          "service": newTokenService.getValue(),
          "token_key": newTokenKey.getValue(),
          "token_secret": newTokenSecret.getValue()
        };
        tokens.post(null, newTokenInfo);
      }, this);
      form.addButton(addTokenBtn);

      return form;
    },

    __createValidTokenForm: function(service, key, secret) {
      let form = new qx.ui.form.Form();

      let tokenService = new qx.ui.form.TextField().set({
        value: service,
        readOnly: true
      });
      form.add(tokenService, this.tr("Service API"));

      let tokenKey = new qx.ui.form.TextField();
      tokenKey.set({
        value: key,
        readOnly: true
      });
      form.add(tokenKey, this.tr("Key"));

      if (secret) {
        let tokenSecret = new qx.ui.form.TextField();
        tokenSecret.set({
          value: secret,
          readOnly: true
        });
        form.add(tokenSecret, this.tr("Secret"));
      }

      let delTokenBtn = new qx.ui.form.Button(this.tr("Delete"));
      delTokenBtn.setWidth(100);
      delTokenBtn.addListener("execute", e => {
        let token = this.__tokenResources.token;
        token.addListenerOnce("delSuccess", eve => {
          this.__rebuildTokensList();
        }, this);
        token.addListenerOnce("delError", eve => {
          console.log(eve);
        });
        token.del({
          "service": service
        });
      }, this);
      form.addButton(delTokenBtn);

      return form;
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
        return qxapp.auth.core.Utils.checkSamePasswords(newPassword, confirm);
      });

      let resetBtn = new qx.ui.form.Button("Reset Password").set({
        allowGrowX: false
      });
      box.add(resetBtn);

      resetBtn.addListener("execute", () => {
        if (manager.validate()) {
          let request = new qxapp.io.request.ApiRequest("/auth/change-password", "POST");
          request.setRequestData({
            "current": currentPassword.getValue(),
            "new": newPassword.getValue(),
            "confirm": confirm.getValue()
          });

          request.addListenerOnce("success", function(e) {
            const res = e.getTarget().getResponse();
            qxapp.component.widget.FlashMessenger.getInstance().log(res.data);

            [currentPassword, newPassword, confirm].forEach(item => {
              item.resetValue();
            });
          }, this);

          request.addListenerOnce("fail", e => {
            const error = e.getTarget().getResponse().error;
            const msg = error ? error["errors"][0].message : this.tr("Failed to reset password");
            qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR");

            [currentPassword, newPassword, confirm].forEach(item => {
              item.resetValue();
            });
          }, this);

          request.send();
        }
      });

      return box;
    }
  }
});
