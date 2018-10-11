/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.NavigationBar", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      maxHeight: 50
    });
    this.getLayout().set({
      spacing: 10,
      alignY: "middle"
    });

    const commonBtnSettings = {
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    };

    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);

    let logo = new qx.ui.basic.Image("qxapp/osparc-white-small.png").set({
      maxHeight: 32,
      maxWidth: 92,
      scale: true
    });
    this.add(logo);

    this.add(new qx.ui.toolbar.Separator());

    let mainViewCaption = this.__mainViewCaption = new qx.ui.basic.Label().set({
      font: navBarLabelFont
    });
    this.add(mainViewCaption);


    this.add(new qx.ui.core.Spacer(5), {
      flex: 1
    });


    let dashboardBtn = new qx.ui.form.Button(this.tr("Dashboard"));
    dashboardBtn.set(commonBtnSettings);
    dashboardBtn.addListener("execute", function() {
      this.fireEvent("DashboardPressed");
    }, this);
    this.add(dashboardBtn);

    this.add(new qx.ui.toolbar.Separator());

    let pubPrjsBtn = new qx.ui.form.Button(this.tr("Public Projects"));
    pubPrjsBtn.set(commonBtnSettings);
    this.add(pubPrjsBtn);

    this.add(new qx.ui.toolbar.Separator());

    let forumBtn = new qx.ui.form.Button(this.tr("Forum"));
    forumBtn.set(commonBtnSettings);
    this.add(forumBtn);

    this.add(new qx.ui.toolbar.Separator());

    let helpBtn = new qx.ui.form.Button(this.tr("Help"));
    helpBtn.set(commonBtnSettings);
    this.add(helpBtn);

    this.add(new qx.ui.toolbar.Separator());

    const dummyUser="bizzy";
    let userLbl = new qx.ui.basic.Label("@" + dummyUser).set({
      minWidth: 20
    });
    this.add(userLbl);

    let userBtn = this.__createUserBtn();
    userBtn.set(commonBtnSettings);
    userBtn.setIcon(qxapp.utils.Avatar.getUrl(dummyUser + "@itis.ethz.ch", 32));
    this.add(userBtn);
  },

  events: {
    "DashboardPressed": "qx.event.type.Event"
  },

  members: {
    __mainViewCaption: null,

    setMainViewCaption: function(newLabel) {
      this.__mainViewCaption.setValue(newLabel);
    },

    __createUserBtn: function() {
      var menu = new qx.ui.menu.Menu();

      // Account Settings
      // ---
      // Groups
      // ---
      // Help
      // Report a Problem
      // About
      // ---
      // Logout

      // TODO: add commands (i.e. short-cut system)
      let preferences = new qx.ui.menu.Button("Account Settings");
      preferences.addListener("execute", this.__onOpenAccountSettings, this);

      let logout = new qx.ui.menu.Button("Logout");
      logout.addListener("execute", function(e) {
        let app = qx.core.Init.getApplication();
        app.logout();
      });

      menu.add(preferences);
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button("Groups"));
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button("Help"));
      menu.add(new qx.ui.menu.Button("Report a Problem"));
      menu.add(new qx.ui.menu.Button("About"));
      menu.addSeparator();
      menu.add(logout);

      let btn = new qx.ui.form.MenuButton(null, null, menu);
      return btn;
    },

    __onOpenAccountSettings: function() {
      if (!this.__preferencesWin) {
        this.__preferencesWin = new qxapp.Preferences();
      }

      let win = this.__preferencesWin;
      if (win) {
        win.open();

        const [left, top] = qxapp.utils.Dom.getCenteredLoc(win.getWidth(), win.getHeight());
        win.moveTo(left, top);
      }
    }
  }
});
