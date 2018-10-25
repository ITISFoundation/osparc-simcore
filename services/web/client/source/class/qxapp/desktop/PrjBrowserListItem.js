/* eslint "qx-rules/no-refs-in-members": "warn" */
qx.Class.define("qxapp.desktop.PrjBrowserListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel],
  include : [qx.ui.form.MModelProperty],

  construct: function() {
    this.base(arguments);

    // create a date format like "October 19, 2018 11:31 AM"
    this._dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("long") + " " +
      qx.locale.Date.getTimeFormat("short")
    );

    let layout = new qx.ui.layout.VBox().set({
      alignY: "middle"
    });
    this._setLayout(layout);

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  events:
  {
    /** (Fired by {@link qx.ui.form.List}) */
    "action" : "qx.event.type.Event"
  },

  properties: {
    appearance :
    {
      refine : true,
      init : "pb-listitem"
    },
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
      check : "Date",
      apply : "_applyCreated",
      nullable : true
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    _dateFormat: null,

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
          control = new qx.ui.basic.Label().set({
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
      icon.set({
        source: value,
        paddingTop: value && value.match(/^@/) ? 30 : 0
      });
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
      if (value) {
        const dateStr = this._dateFormat.format(value);
        label.setValue("Created on: <b>" + dateStr + "</b>");
      } else {
        label.resetValue();
      }
    },
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    /**
     * Event handler for the pointer over event.
     */
    _onPointerOver: function() {
      this.addState("hovered");
    },


    /**
     * Event handler for the pointer out event.
     */
    _onPointerOut : function() {
      this.removeState("hovered");
    }
  },
  destruct : function() {
    this._dateFormat.dispose();
    this._dateFormat = null;
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
