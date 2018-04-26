qx.Class.define("qxapp.layout.NavigationBar", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.HBox(10)
    });

    this.set({
      backgroundColor: "yellow",
      padding: 10
    });

    var button = new qx.ui.form.Button("Home");
    button.set({
      maxWidth: 75,
      maxHeight: 75,
      alignY:"middle"
    });
    let scope = this;
    button.addListener("execute", function() {
      scope.fireEvent("HomePressed");
    }, scope);
    this.add(button);

    var label = new qx.ui.basic.Label("Showing: ");
    label.set({
      alignY:"middle"
    });
    this.add(label);

    this._currentState = new qx.ui.basic.Label();
    this._currentState.set({
      alignY:"middle"
    });
    this.add(this._currentState);
  },

  events: {
    "HomePressed": "qx.event.type.Event"
  },

  members: {
    setCurrentStatus: function(newLabel) {
      this._currentState.setValue(newLabel);
    }
  }
});
