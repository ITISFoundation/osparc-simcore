/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.Preferences", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base(arguments, this.tr("Account Settings"));

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
    _data: null,

    __createPage: function(name, iconSrc = null) {
      let page = new qx.ui.tabview.Page(name, iconSrc);
      page.setLayout(new qx.ui.layout.VBox(10).set({
        spacing: 10,
        alignX: "center"
      }));

      // title
      page.add(new qx.ui.basic.Label("<h3>" + name + " Settings</h3>").set({
        rich: true
      }));

      // spacer
      page.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
      return page;
    },

    __getGeneral: function() {
      const iconUrl = qxapp.utils.Placeholders.getIcon("ion-ios-settings", 32);
      let page = this.__createPage("General", iconUrl);

      // content
      let username = new qx.ui.form.TextField().set({
        value: "bizzy",
        placeholder: "User Name"
      });
      page.add(username);

      let fullname = new qx.ui.form.TextField().set({
        placeholder: "Full Name"
      });

      page.add(fullname);

      let email = new qx.ui.form.TextField().set({
        placeholder: "Email"
      });
      page.add(email);

      let img = new qx.ui.basic.Image().set({
        source: qxapp.utils.Placeholders.getGravatar(email.getValue() || "bizzy@itis.ethz.ch", 200)
      });
      page.add(img);

      return page;
    },

    __getSecurity: function() {
      const iconUrl = qxapp.utils.Placeholders.getIcon("fa-lock", 32);
      let page = this.__createPage("Security", iconUrl);

      // content
      page.add(new qx.ui.form.PasswordField().set({
        placeholder: "Password"
      }));

      page.add(new qx.ui.form.PasswordField().set({
        placeholder: "Re-type Password"
      }));

      page.add(new qx.ui.basic.Atom("<h3>DAT-CORE</h3>").set({
        rich: true
      }));

      let tokens = new qx.ui.form.TextField();
      tokens.set({
        placeholder: "Personal Access Token"
      });
      page.add(tokens);

      return page;
    },

    __getDisplay: function() {
      const iconUrl = qxapp.utils.Placeholders.getIcon("fa-eye", 32);
      let page = this.__createPage("Display", iconUrl);
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
      const iconUrl = qxapp.utils.Placeholders.getIcon("fa-rebel", 32);
      let page = this.__createPage("Advanced", iconUrl);

      return page;
    }
  }

});
