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
    __validTokens: null,

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

      page.add(new qx.ui.form.renderer.Single(form).set({
        alignY: "bottom",
        padding: 0
      }));

      let img = new qx.ui.basic.Image().set({
        source: qxapp.utils.Avatar.getUrl(email.getValue(), 200)
      });
      page.add(img);

      return page;
    },

    __getSecurity: function() {
      const iconUrl = "@FontAwesome5Solid/shield-alt/24";
      let page = this.__createPage(this.tr("Security"), iconUrl);

      // content
      // page.add(new qx.ui.form.PasswordField().set({
      //   placeholder: "Password"
      // }));

      // page.add(new qx.ui.form.PasswordField().set({
      //   placeholder: "Re-type Password"
      // }));

      page.add(new qx.ui.basic.Atom("<h3>DAT-CORE</h3>").set({
        rich: true
      }));

      let newTokenGrp = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      let newTokenPass = new qx.ui.form.PasswordField();
      newTokenPass.set({
        placeholder: "Personal Access Token",
        alignY: "bottom"
      });
      newTokenGrp.add(newTokenPass, {
        flex: 1
      });
      let newTokenBtn = new qx.ui.toolbar.Button(null, "@FontAwesome5Solid/plus/12");
      newTokenBtn.addListener("execute", e => {
        let tokens = this.__tokenResources.tokens;
        tokens.addListenerOnce("postSuccess", ev => {
          newTokenPass.resetValue();
          let tokensList = ev.getRequest().getResponse().data;
          console.log(tokensList);
          this.__reloadTokens();
        }, this);
        tokens.addListenerOnce("getError", ev => {
          console.log(ev);
        });
        tokens.post(newTokenPass.getValue());
      }, this);
      newTokenGrp.add(newTokenBtn);
      page.add(newTokenGrp);

      this.__validTokens = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      page.add(this.__validTokens);
      this.__reloadTokens();

      return page;
    },

    __reloadTokens: function() {
      this.__validTokens.removeAll();

      let tokens = this.__tokenResources.tokens;
      tokens.addListenerOnce("getSuccess", e => {
        let tokensList = e.getRequest().getResponse().data;
        for (let i=0; i<tokensList.length; i++) {
          let validTokenGrp = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          let validToken = new qx.ui.form.TextField();
          validToken.set({
            value: tokensList[i]["service"] + ": " + tokensList[i]["token_key"],
            enable: false,
            alignY: "bottom"
          });
          validTokenGrp.add(validToken, {
            flex: 1
          });
          let newTokenBtn = new qx.ui.toolbar.Button(null, "@FontAwesome5Solid/trash/12");
          newTokenBtn.addListener("execute", ev => {
            let token = this.__tokenResources.token;
            token.addListenerOnce("delSuccess", eve => {
              this.__reloadTokens();
            }, this);
            token.addListenerOnce("delError", eve => {
              console.log(eve);
            });
            token.del();
          }, this);
          validTokenGrp.add(newTokenBtn);
          this.__validTokens.add(validTokenGrp);
        }
      }, this);
      tokens.addListenerOnce("getError", e => {
        console.log(e);
      });
      tokens.get();
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
