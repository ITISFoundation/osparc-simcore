/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.Preferences", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base(arguments, this.tr("Account Settings"));

    this.__tokenResources = qxapp.io.rest.ResourceFactory.getInstance().createTokenResources();
    // this.__tokenResources.token
    // this.__tokenResources.tokens

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
    tabView.add(this.__getGeneral());
    tabView.add(this.__getSecurity());
    // TODO: groups?
    // TODO: notifications?
    tabView.add(this.__getDisplay());
    tabView.add(this.__getAdvanced());

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
      page.add(new qx.ui.basic.Label("<h3>" + name + " " + this.tr("Settings") + "</h3>").set({
        rich: true
      }));

      // spacer
      page.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
      return page;
    },

    __getGeneral: function() {
      const iconUrl = "@FontAwesome5Solid/sliders-h/24";
      let page = this.__createPage(this.tr("General"), iconUrl);

      const userEmail = qxapp.auth.Data.getInstance().getEmail();

      let form = new qx.ui.form.Form();
      // content
      let username = new qx.ui.form.TextField().set({
        value: userEmail.split("@")[0],
        placeholder: "User Name",
        readOnly: true
      });
      form.add(username, "Username");

      // let fullname = new qx.ui.form.TextField().set({
      //   placeholder: "Full Name"
      // });

      // page.add(fullname);

      let email = new qx.ui.form.TextField().set({
        value: userEmail,
        placeholder: "Email",
        readOnly: true
      });
      form.add(email, this.tr("Email"));

      page.add(new qx.ui.form.renderer.Single(form));

      let img = new qx.ui.basic.Image().set({
        source: qxapp.utils.Avatar.getUrl(email.getValue(), 200)
      });
      page.add(img);

      return page;
    },

    __getSecurity: function() {
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
          let emptyForm = this.__getEmptyTokenForm();
          this.__tokensList.add(new qx.ui.form.renderer.Single(emptyForm));
        } else {
          for (let i=0; i<tokensList.length; i++) {
            const token = tokensList[i];
            let tokenForm = this.__getValidTokenForm(token["service"], token["token_key"], token["token_secret"]);
            this.__tokensList.add(new qx.ui.form.renderer.Single(tokenForm));
          }
        }
      }, this);
      tokens.addListenerOnce("getError", e => {
        console.log(e);
      });
      tokens.get();
    },

    __getEmptyTokenForm: function() {
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

    __getValidTokenForm: function(service, key, secret) {
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

    __getDisplay: function() {
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

    __getAdvanced: function() {
      const iconUrl = "@FontAwesome5Solid/flask/24";
      let page = this.__createPage(this.tr("Experimental"), iconUrl);

      return page;
    }
  }

});
