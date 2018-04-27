qx.Class.define("qxapp.layout.NavigationBar", {
  extend: qx.ui.container.Composite,

  construct: function () {
    this.base(arguments, new qx.ui.layout.HBox());

    this.set({
      backgroundColor: "#00264d", // FIXME: add theme color
      textColor: "white",
      paddingLeft: 10,
      paddingRight: 10,
      maxHeight: 50
    });
    this.getLayout().set({
      spacing: 10,
      alignY: "middle",
    });

    const commonBtnSettings = {
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32,
    }

    let homeBtn = new qx.ui.form.Button();
    homeBtn.set(commonBtnSettings);
    homeBtn.setIcon(qxapp.utils.Placeholders.getIcon("ion-home", 32));
    this.add(homeBtn);

    this._currentState = new qx.ui.basic.Label().set({
      minWidth: 20,
    });
    this.add(this._currentState);

    this.add(new qx.ui.core.Spacer(5), {
      flex: 1
    });

    let userLbl = new qx.ui.basic.Label("@bizzi").set({
      minWidth: 20,
    });
    this.add(userLbl);

    let userBtn = this.__createUserBtn()
    userBtn.set(commonBtnSettings);
    userBtn.setIcon(qxapp.utils.Placeholders.getGravatar("bizzi@simcore.io", 32));
    this.add(userBtn);


    // Connect listeners
    let scope = this;
    homeBtn.addListener("execute", function () {
      scope.fireEvent("HomePressed");
    }, scope);

  },

  events: {
    "HomePressed": "qx.event.type.Event"
  },

  members: {

    setCurrentStatus: function (newLabel) {
      this._currentState.setValue("Showing: " + newLabel);
    },

    __createUserBtn: function () {
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

      menu.add(preferences);
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button("Groups"));
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button("Help"));
      menu.add(new qx.ui.menu.Button("Report a Problem"));
      menu.add(new qx.ui.menu.Button("About"));
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button("Logout"));

      var button = new qx.ui.form.MenuButton(null, null, menu);
      return button;
    },

    __onOpenAccountSettings: function () {
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
