qx.Class.define("qxapp.auth.AuthView", {
  extend: qx.ui.container.Composite,

  construct : function() {
    this.base(arguments);

    let layout = new qx.ui.layout.Grid();
    layout.setRowFlex(0, 1);
    layout.setColumnFlex(0, 1);
    this.setLayout(layout);

    this.__next(this.__buildLoginPage());
  },

  events: {
    "done": "qx.event.type.Data"
  },

  members: {
    __current: null,

    __buildLoginPage: function() {
      let page = new qxapp.auth.ui.LoginPage();

      page.addListener("done", function(msg) {
        // if msg, flash it
        this.fireDataEvent("done", msg);
      }, this);

      page.addListener("toReset", function(e) {
        this.__next(this.__buildResetPage());
      }, this);

      page.addListener("toRegister", function(e) {
        this.__next(this.__buildRegistrationPage());
      }, this);

      return page;
    },

    __buildResetPage: function() {
      let page = new qxapp.auth.ui.ResetPassPage();

      page.addListener("done", function(msg) {
        this.__next(this.__buildLoginPage(), msg);
      }, this);

      return page;
    },

    __buildRegistrationPage: function() {
      let page = new qxapp.auth.ui.RegistrationPage();

      page.addListener("done", function(msg) {
        this.__next(this.__buildLoginPage(), msg);
      }, this);

      return page;
    },

    __next: function(page, flashMsg) {
      let prev = this.__current;
      if (prev!==page) {
        if (prev) {
          this.remove(prev);
        }

        this.add(page, {
          row: 0,
          column: 0
        });
        this.__current = page;

        if (prev) {
          // ??
          // prev.destroy();
        }
      }
    }
  }
});
