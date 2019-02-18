/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by PrjBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("qxapp.desktop.PrjBrowserListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel],
  include : [qx.ui.form.MModelProperty],

  construct: function() {
    this.base(arguments);

    // create a date format like "Oct. 19, 2018 11:31 AM"
    this._dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("medium") + " " +
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
    appearance: {
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

    lastChangeDate: {
      check : "Date",
      apply : "_applylastChangeDate",
      nullable : true
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    _dateFormat: null,
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

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
        case "lastChangeDate":
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

    _applylastChangeDate: function(value, old) {
      let label = this.getChildControl("lastChangeDate");
      if (value) {
        const dateStr = this._dateFormat.format(value);
        label.setValue("Last change: <b>" + dateStr + "</b>");
      } else {
        label.resetValue();
      }
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
