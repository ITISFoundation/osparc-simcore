qx.Class.define("qxapp.component.widget.inputs.NodeOutputListItemIcon", {
  extend: qx.ui.form.ListItem,

  construct: function() {
    this.base(arguments);

    let layout = new qx.ui.layout.VBox().set({
      alignY: "middle"
    });
    this._setLayout(layout);
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image(this.getIcon()).set({
            alignX: "center"
          });
          this._add(control);
          break;
        case "label":
          control = new qx.ui.basic.Label(this.getLabel()).set({
            alignX: "center",
            rich: true,
            allowGrowY: false
          });
          this._add(new qx.ui.core.Spacer(1, 5));
          this._add(control);
          this._add(new qx.ui.core.Spacer(1, 15));
          break;
      }

      return control || this.base(arguments, id);
    }
  }
});
