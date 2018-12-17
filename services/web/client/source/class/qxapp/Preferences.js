/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.Preferences", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base(arguments, this.tr("Account Settings"));

    this.__tokenResources = qxapp.io.rest.ResourceFactory.getInstance().createTokenResources();

    // window
    // TODO: fix-sized modal preference window
    this.set({
      modal: true,
      width: 500,
      height: 500 * 1.2,
      showClose: true,
      showMaximize: false,
      showMinimize: false,
      resizable: false
    });
    this.setLayout(new qx.ui.layout.VBox(10));


    var tabView = new qx.ui.tabview.TabView().set({
      barPosition: "left"
    });
    tabView.add(this.__createProfile());
    tabView.add(this.__createSecurity());
    // TODO: groups?
    // TODO: notifications?
    tabView.add(this.__createDisplay());
    tabView.add(this.__createExperimental());

    this.add(tabView, {
      flex: 1
    });
  },

  members: {
    __tokenResources: null,
    __tokensList: null,

    __createPage: function(name, iconSrc = null) {
      let page = new qx.ui.tabview.Page(name, iconSrc);
      page.setLayout(new qx.ui.layout.VBox(10).set({
        spacing: 10,
        alignX: "center"
      }));

      // title
      page.add(new qx.ui.basic.Label(name).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-16"])
      }));

      // spacer
      page.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
      return page;
    },

    __createProfile: function() {
      const iconUrl = "@FontAwesome5Solid/sliders-h/24";
      let page = this.__createPage(this.tr("Profile"), iconUrl);

      page.add(this.__createProfileUser());
      page.add(this.__createProfilePassword());

      return page;
    },

    __createProfileUser: function() {
      // layout
      let box = new qx.ui.groupbox.GroupBox("User");
      box.setLayout(new qx.ui.layout.VBox(10));

      let email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Email")
      });

      let firstName = new qx.ui.form.TextField().set({
        placeholder: this.tr("First Name")
      });

      let lastName = new qx.ui.form.TextField().set({
        placeholder: this.tr("Last Name")
      });

      let role = new qx.ui.form.TextField().set({
        readOnly: true
      });

      let form = new qx.ui.form.Form();
      form.add(email, "", null, "email");
      form.add(firstName, "", null, "firstName");
      form.add(lastName, "", null, "lastName");
      form.add(role, "", null, "role");

      box.add(new qx.ui.form.renderer.Single(form));

      let img = new qx.ui.basic.Image().set({
        alignX: "center"
      });
      box.add(img);

      let updateBtn = new qx.ui.form.Button("Update Profile").set({
        allowGrowX: false
      });
      box.add(updateBtn);

      // binding to a model
      let raw = {
        "first_name": null,
        "last_name": null,
        "email": null,
        "role": null
      };

      if (qx.core.Environment.get("qx.debug")) {
        raw = {
          "first_name": "Bizzy",
          "last_name": "Zastrow",
          "email": "bizzy@itis.ethz.ch",
          "role": "Tester"
        };
      }
      let model = qx.data.marshal.Json.createModel(raw);
      let controller = new qx.data.controller.Object(model);

      controller.addTarget(email, "value", "email", true);
      controller.addTarget(firstName, "value", "first_name", true, null, {
        converter: function(data) {
          return data.replace(/^\w/, c => c.toUpperCase());
        }
      });
      controller.addTarget(lastName, "value", "last_name", true);
      controller.addTarget(role, "value", "role", false);
      controller.addTarget(img, "source", "email", false, {
        converter: function(data) {
          return qxapp.utils.Avatar.getUrl(email.getValue(), 150);
        }
      });

      // validation
      let manager = new qx.ui.form.validation.Manager();
      manager.add(email, qx.util.Validate.email());
      manager.add(firstName, qx.util.Validate.string());
      manager.add(lastName, qx.util.Validate.string());

      // update trigger
      updateBtn.addListenerOnce("execute", function() {
        if (manager.validate()) {
          let request = new qxapp.io.request.ApiRequest("/auth/change-email", "POST");
          request.setRequestData({
            "email": model.email
          });

          request.addListenerOnce("success", function(e) {
            const res = e.getTarget().getResponse();
            qxapp.component.widget.FlashMessenger.getInstance().log(res.data);
          }, this);

          request.addListenerOnce("fail", function(e) {
            const res = e.getTarget().getResponse();
            const msg = res.error|| "Failed to update email";
            email.set({
              invalidMessage: msg,
              valid: false
            });
          }, this);

          request.send();
        }
      }, this);

      // get values from server
      let request = new qxapp.io.request.ApiRequest("/me", "GET");
      request.addListenerOnce("success", function(e) {
        const data = e.getTarget().getResponse()["data"];
        model.set({
          "first_name": data["first_name"],
          "last_name": data["last_name"],
          "email": data["login"],
          "role": data["role"]
        });
      });

      request.addListenerOnce("fail", function(e) {
        const res = e.getTarget().getResponse();
        const msg = res.error || "Failed to update profile";
        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "Error", "user");
      });

      request.send();
      return box;
    },

    __createProfilePassword: function() {
      // layout
      let box = new qx.ui.groupbox.GroupBox(this.tr("Password"));
      box.setLayout(new qx.ui.layout.VBox(10));

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
      manager.add(newPassword, function(value, itemForm) {
        return qxapp.auth.core.Utils.checkPasswordSecure(value, itemForm);
      });
      manager.setValidator(function(_itemForms) {
        return qxapp.auth.core.Utils.checkSamePasswords(newPassword, confirm);
      });

      let resetBtn = new qx.ui.form.Button("Reset Password").set({
        allowGrowX: false
      });
      box.add(resetBtn);

      resetBtn.addListener("execute", function() {
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
            const res = e.getTarget().getResponse();
            const msg = res.error || "Failed to update password";
            qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR");

            [currentPassword, newPassword, confirm].forEach(item => {
              item.resetValue();
            });
          }, this);

          request.send();
        }
      });

      return box;
    },

    __createSecurity: function() {
      const iconUrl = "@FontAwesome5Solid/shield-alt/24";
      let page = this.__createPage(this.tr("Security"), iconUrl);

      const title14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"]);
      page.add(new qx.ui.basic.Label("API Tokens").set({
        font: title14Font
      }));

      this.__tokensList = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      page.add(this.__tokensList);

      this.__reloadTokens();

      return page;
    },

    __reloadTokens: function() {
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
        console.log(e);
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
        placeholder: "introduce token key here"
      });
      form.add(newTokenKey, this.tr("Key"));

      let newTokenSecret = new qx.ui.form.TextField();
      newTokenSecret.set({
        placeholder: "introduce token secret here"
      });
      form.add(newTokenSecret, this.tr("Secret"));

      let addTokenBtn = new qx.ui.form.Button(this.tr("Add"));
      addTokenBtn.setWidth(100);
      addTokenBtn.addListener("execute", e => {
        let tokens = this.__tokenResources.tokens;
        tokens.addListenerOnce("postSuccess", ev => {
          this.__reloadTokens();
        }, this);
        tokens.addListenerOnce("getError", ev => {
          console.log(ev);
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
          this.__reloadTokens();
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

    __createDisplay: function() {
      const iconUrl = "@FontAwesome5Solid/eye/24";
      let page = this.__createPage(this.tr("Display"), iconUrl);
      let themes = qx.Theme.getAll();

      let select = new qx.ui.form.SelectBox("Theme");
      page.add(select);

      let themeMgr = qx.theme.manager.Meta.getInstance();
      let currentTheme = themeMgr.getTheme();


      for (let key in themes) {
        let theme = themes[key];
        if (theme.type === "meta") {
          let item = new qx.ui.form.ListItem(theme.name);
          item.setUserData("theme", theme.name);
          select.add(item);
          if (theme.name == currentTheme.name) {
            select.setSelection([item]);
          }
        }
      }

      select.addListener("changeSelection", function(evt) {
        var selected = evt.getData()[0].getUserData("theme");
        var theme = qx.Theme.getByName(selected);
        if (theme) {
          themeMgr.setTheme(theme);
        }
      });
      return page;
    },

    __createExperimental: function() {
      const iconUrl = "@FontAwesome5Solid/flask/24";
      let page = this.__createPage(this.tr("Experimental"), iconUrl);

      return page;
    }
  }

});
