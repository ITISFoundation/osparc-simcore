qx.Class.define("osparc.widget.cell.Editor", {
  extend: qx.ui.core.Widget,

  construct: function(cellData) {
    this.base(arguments);

    this.setHandler(cellData);

    this._setLayout(new qx.ui.layout.VBox(10));

    let controls = this._createChildControlImpl("controls");
    this._add(controls);
    this._add(cellData.getNode().getIFrame(), {
      flex: 1
    });
  },

  properties: {
    handler: {
      check: "osparc.widget.cell.Handler",
      nullable: false
    }
  },

  events: {
    "backToGrid": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "controls": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());

          let back = new qx.ui.form.Button(this.tr("Back to grid"));
          back.addListener("execute", e => {
            this.fireEvent("backToGrid");
          }, this);
          control.add(back);

          control.add(new qx.ui.core.Spacer(100, null));

          let titleField = new qx.ui.basic.Label().set({
            alignY: "middle",
            minWidth: 200
          });
          this.getHandler().getNode()
            .bind("label", titleField, "value");
          control.add(titleField);

          break;
        }
      }

      return control || this.base(arguments, id);
    }
  }
});
