qx.Class.define("qxapp.desktop.PrjBrowserListItem", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    // create a date format like "October 19, 2018 11:31 AM"
    this._dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("long") + " " +
      qx.locale.Date.getTimeFormat("short")
    );

    let layout = new qx.ui.layout.VBox();
    this._setLayout(layout);
  },

  properties: {
    icon: {
      check: "String",
      apply : "_applyIcon",
      nullable : true
    },

    prjTitle: {
      check: "String",
      apply : "_applyPrjTitle",
      nullable : true
    },

    creator: {
      check: "String",
      apply : "_applyCreator",
      nullable : true
    },

    created: {
      // check : "Date",
      check : "String",
      apply : "_applyCreated",
      nullable : true
    }
  },

  members: {
    _dateFormat : null,

    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          {
            control = new qx.ui.basic.Image(this.getIcon());
            this._add(control);
            let dummyProgress = new qx.ui.indicator.ProgressBar().set({
              height: 10,
              maximum: 100,
              value: Math.floor(Math.random() * 101)
            });
            this._add(dummyProgress);
          }
          break;
        case "prjTitle":
          control = new qx.ui.basic.Label(this.getPrjTitle()).set({
            rich: true,
            allowGrowY: false
          });
          this._add(new qx.ui.core.Spacer(null, 5));
          this._add(control);
          this._add(new qx.ui.core.Spacer(null, 5));
          break;
        case "creator":
          control = new qx.ui.basic.Label(this.getCreator()).set({
            rich: true,
            allowGrowY: false
          });
          this._addAt(control);
          break;
        case "created":
          control = new qx.ui.basic.Label(this.getCreated()).set({
            rich: true,
            allowGrowY: false
          });
          this._addAt(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    _applyIcon: function(value, old) {
      let icon = this.getChildControl("icon");
      icon.setSource(value);
    },

    _applyPrjTitle: function(value, old) {
      let label = this.getChildControl("prjTitle");
      label.setValue(value);
    },

    _applyCreator: function(value, old) {
      let label = this.getChildControl("creator");
      label.setValue(value);
    },

    _applyCreated: function(value, old) {
      let label = this.getChildControl("created");
      // label.setValue(this._dateFormat.format(value));
      label.setValue(value);
    },

    destruct : function() {
      this._dateFormat.dispose();
      this._dateFormat = null;
    }
  }
});
