/* eslint no-warning-comments: "off" */

const NAVIGATION_BUTTON_HEIGHT = 32;

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
      minHeight: NAVIGATION_BUTTON_HEIGHT
    };


    let logo = new qx.ui.basic.Image("qxapp/osparc-white-small.png").set({
      maxHeight: NAVIGATION_BUTTON_HEIGHT,
      maxWidth: 92,
      scale: true
    });
    this.add(logo);

    this.add(new qx.ui.toolbar.Separator());

    let hBox = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    let mainViewCaptionLayout = this.__mainViewCaptionLayout = new qx.ui.container.Composite(hBox);
    this.add(mainViewCaptionLayout);


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

    const userEmail = qxapp.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";

    let userLbl = new qx.ui.basic.Label(userEmail.split("@")[0]).set({
      minWidth: 20
    });
    this.add(userLbl);

    let userBtn = this.__createUserBtn();
    userBtn.set(commonBtnSettings);

    userBtn.setIcon(qxapp.utils.Avatar.getUrl(userEmail, NAVIGATION_BUTTON_HEIGHT));
    this.add(userBtn);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data",
    "DashboardPressed": "qx.event.type.Event"
  },

  members: {
    __mainViewCaptionLayout: null,

    setMainViewCaption: function(newLabel) {
      this.__mainViewCaptionLayout.removeAll();
      if (typeof newLabel === "string") {
        this.__showMainViewCaptionAsText(newLabel);
      } else if (Array.isArray(newLabel)) {
        this.__showMainViewCaptionAsButtons(newLabel);
      }
    },

    __showMainViewCaptionAsText: function(newLabel) {
      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      let mainViewCaption = this.__mainViewCaption = new qx.ui.basic.Label(newLabel).set({
        font: navBarLabelFont
      });
      this.__mainViewCaptionLayout.add(mainViewCaption);
    },

    __showMainViewCaptionAsButtons: function(newLabels) {
      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      for (let i=0; i<newLabels.length; i++) {
        const newLabel = newLabels[i];
        const label = Object.values(newLabel)[0];
        const nodeId = Object.keys(newLabel)[0];
        let btn = new qx.ui.form.Button(label).set({
          maxHeight: NAVIGATION_BUTTON_HEIGHT
        });
        btn.addListener("execute", function() {
          this.fireDataEvent("NodeDoubleClicked", nodeId);
        }, this);
        this.__mainViewCaptionLayout.add(btn);

        if (i<newLabels.length-1) {
          let mainViewCaption = this.__mainViewCaption = new qx.ui.basic.Label(">").set({
            font: navBarLabelFont
          });
          this.__mainViewCaptionLayout.add(mainViewCaption);
        }
      }
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
      logout.addListener("execute", e => {
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
        win.center();
        win.open();
      }
    }
  }
});
