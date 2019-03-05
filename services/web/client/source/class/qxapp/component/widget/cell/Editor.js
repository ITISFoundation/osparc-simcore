qx.Class.define("qxapp.component.widget.cell.Editor", {
  extend: qx.ui.core.Widget,

  construct: function(cellData) {
    this.base(arguments);

    this.setHandler(cellData);

    this._setLayout(new qx.ui.layout.VBox(10));

    let controls = this._createChildControlImpl("controls");
    this._addAt(controls, 0);

    // let loadingUri = qx.util.ResourceManager.getInstance().toUri("dashGrid/raw/index.html");
    let loadingUri = qx.util.ResourceManager.getInstance().toUri("qxapp/loading/loader.html");
    let iframe = new qx.ui.embed.Iframe(loadingUri);
    iframe.setBackgroundColor("transparent");
    this.setContent(iframe);
  },

  properties: {
    handler: {
      check: "qxapp.component.widget.cell.Handler",
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

          control.add(new qx.ui.core.Spacer(), {
            flex: 1
          });

          let titleField = this.__titleField = new qx.ui.form.TextField(this.tr("title")).set({
            maxLength: 25,
            minWidth: 200
          });
          titleField.addListener("changeValue", e => {
            this.getHandler().setTitle(e.getData());
          }, this);
          control.add(titleField);

          control.add(new qx.ui.core.Spacer(), {
            flex: 1
          });

          let change = new qx.ui.form.Button(this.tr("Change content"));
          change.addListener("execute", e => {
            this.getHandler().createRandomData();
            this.setContent(this.getHandler().getEditor());
          }, this);
          control.add(change);

          break;
        }
      }

      return control || this.base(arguments, id);
    },

    getTitle: function() {
      this.__titleField.getValue();
    },

    setContent: function(content) {
      if (this._getChildren().length > 1) {
        this._removeAt(1);
      }
      this._addAt(content, 1, {
        flex: 1
      });
    }
  }
});
