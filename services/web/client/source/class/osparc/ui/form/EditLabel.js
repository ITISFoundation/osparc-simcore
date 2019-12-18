/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.form.EditLabel", {
  extend: qx.ui.core.Widget,
  construct: function(value) {
    this.base(arguments);
    if (value) {
      this.setValue(value);
    }
    this._setLayout(new qx.ui.layout.HBox().set({
      alignY: "middle"
    }));
    this.__loadingIcon = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/12");
    this.__loadingIcon.getContentElement().addClass("rotate");
    this.__renderLayout();
  },
  events: {
    "editValue": "qx.event.type.Data"
  },
  statics: {
    modes: {
      DISPLAY: "display",
      EDIT: "edit"
    }
  },
  properties: {
    appearance: {
      init: "editlabel",
      refine: true
    },
    mode: {
      check: "String",
      nullable: false,
      init: "display",
      apply: "_applyMode"
    },
    value: {
      check: "String",
      event: "changeValue",
      init: ""
    },
    fetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyFetching"
    }
  },
  members: {
    __label: null,
    __input: null,
    __labelWidth: null,
    __renderLayout: function() {
      this._removeAll();
      switch (this.getMode()) {
        case this.self().modes.EDIT:
          this._add(this.getChildControl("input"));
          if (this.__labelWidth) {
            this.__input.setWidth(this.__labelWidth);
          }
          this.__input.focus();
          this.__label.removeState("hovered");
          break;
        default:
          this._add(this.getChildControl("label"));
      }
    },
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          if (this.__label === null) {
            this.__label = new qx.ui.basic.Label(this.getValue());
            this.__label.addListener("pointerover", () => this.__label.addState("hovered"), this);
            this.__label.addListener("pointerout", () => this.__label.removeState("hovered"), this);
            this.__label.addListener("tap", () => this.setMode(this.self().modes.EDIT), this);
            this.bind("value", this.__label, "value");
          }
          control = this.__label;
          break;
        case "input":
          if (this.__input === null) {
            this.__input = new qx.ui.form.TextField(this.getValue());
            this.__input.addListener("keydown", evt => {
              if (evt.getKeyIdentifier() === "Enter") {
                this.setMode(this.self().modes.DISPLAY);
              }
            }, this);
            this.__input.addListener("focusout", () => this.setMode(this.self().modes.DISPLAY), this);
            this.__input.addListener("focus", () => this.__input.selectAllText(), this);
            this.__input.addListener("changeValue", evt => this.fireDataEvent("editValue", evt.getData()), this);
          }
          control = this.__input;
          break;
      }
      return control || this.base(arguments, id);
    },
    _applyMode: function(mode) {
      if (mode === this.self().modes.EDIT) {
        this.__labelWidth = this.__label.getSizeHint().width;
      }
      this.__renderLayout();
    },
    _applyFetching: function(isFetching) {
      if (isFetching) {
        this.__label.setEnabled(false);
        this._add(this.__loadingIcon);
      } else {
        this.__label.setEnabled(true);
        this._remove(this.__loadingIcon);
      }
    }
  }
});
