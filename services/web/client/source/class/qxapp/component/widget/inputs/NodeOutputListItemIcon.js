qx.Class.define("qxapp.component.widget.inputs.NodeOutputListItemIcon", {
  extend: qx.ui.form.ListItem,

  construct: function() {
    this.base(arguments);

    let layout = new qx.ui.layout.VBox().set({
      alignY: "middle"
    });
    this._setLayout(layout);
  },
  /*
  properties: {
    iconPath: {
      check: "String",
      apply: "_applyIconPath",
      nullable: true
    }
  },
  */
  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "iconPath":
          control = new qx.ui.basic.Image(this.getIconPath());
          this._add(control);
          break;
        case "label":
          control = new qx.ui.basic.Label(this.getLabel());
          this._add(new qx.ui.core.Spacer(1, 5));
          this._add(control);
          this._add(new qx.ui.core.Spacer(1, 15));
          break;
      }

      return control || this.base(arguments, id);
    },

    _setGap: function(value, old) {
      return;
    }

    /*
    _applyIconPath: function(value, old) {
      let icon = this.getChildControl("iconPath");
      icon.set({
        source: value,
        paddingTop: value && value.match(/^@/) ? 30 : 0
      });
    }
    */
  }
});
