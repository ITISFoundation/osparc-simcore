/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Renders a label and an input combined widget. The idea is to be able to edit a label quickly. Fires an event
 * whenever the input is modified to be able to update the value of the label externally or to trigger some other
 * logic (like API calls).
 */
qx.Class.define("osparc.ui.form.EditLabel", {
  extend: qx.ui.core.Widget,
  /**
   * The constructor can be provided with an initial value for the label.
   * @param {String} value This will be the initial value of the label
   */
  construct: function(value) {
    this.base(arguments);
    if (value) {
      this.setValue(value);
    }
    this._setLayout(new qx.ui.layout.HBox().set({
      alignY: "middle"
    }));
    this.setCursor("text");
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
    /**
     * Controls the two modes of the widget. In edit mode, it shows an input, in display mode,
     * it shows the edited label.
     */
    mode: {
      check: "String",
      nullable: false,
      init: "display",
      apply: "_applyMode"
    },
    /**
     * Master value of the widget. The label in display mode will always show this value.
     */
    value: {
      check: "String",
      event: "changeValue",
      init: "",
      apply: "_applyValue"
    },
    /**
     * When set to true, adds a little spinner to indicate the the value is being updated, for example
     * while waiting for an API call to resolve.
     */
    fetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyFetching"
    },
    /**
     * Lets you choose the font for the label in display mode.
     */
    labelFont: {
      check: "Font",
      apply: "_applySpecificFont"
    },
    /**
     * Lets you choose the font for the input in edit mode.
     */
    inputFont: {
      check: "Font",
      apply: "_applySpecificFont"
    },
    /**
     * Enables the edit mode. If false, the label is not editable.
     */
    editable: {
      check: "Boolean",
      init: true,
      nullable: false,
      apply: "_applyEditable"
    }
  },
  members: {
    __label: null,
    __input: null,
    __labelWidth: null,
    __loadingIcon: null,
    /**
     * This method takes charge of rendering the widget. It relies on the property mode
     * to render the correct version of the widget.
     */
    __renderLayout: function() {
      switch (this.getMode()) {
        case this.self().modes.EDIT:
          this.getChildControl("input").show();
          this.getChildControl("label").exclude();
          if (this.__labelWidth) {
            this.__input.setWidth(this.__labelWidth);
          }
          this.__input.focus();
          this.__label.removeState("hovered");
          break;
        default:
          this.getChildControl("label").show();
          this.getChildControl("input").exclude();
      }
    },
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          if (this.__label === null) {
            this.__label = new qx.ui.basic.Label(this.getValue());
            if (this.isEditable()) {
              this.__label.addState("editable");
            }
            this.__label.addListener("pointerover", () => this.__label.addState("hovered"), this);
            this.__label.addListener("pointerout", () => this.__label.removeState("hovered"), this);
            this.__label.addListener("tap", () => this.setMode(this.isEditable() ? this.self().modes.EDIT : this.self().modes.DISPLAY), this);
            this.bind("value", this.__label, "value");
            this._add(this.__label);
          }
          control = this.__label;
          break;
        case "input":
          if (this.__input === null) {
            this.__input = new qx.ui.form.TextField(this.getValue());
            this.__input.addListener("focusout", () => this.setMode(this.self().modes.DISPLAY), this);
            this.__input.addListener("focus", () => this.__input.selectAllText(), this);
            this.__input.addListener("changeValue", evt => {
              this.setMode(this.self().modes.DISPLAY);
              this.fireDataEvent("editValue", evt.getData());
            }, this);
            this.__input.addListener("keydown", e => {
              if (e.getKeyIdentifier() === "Enter") {
                this.setMode(this.self().modes.DISPLAY);
              }
            }, this);
            this._add(this.__input);
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
    },
    _applyValue: function(value) {
      this.setMode(this.self().modes.DISPLAY);
      if (this.__input) {
        this.__input.setValue(value);
      }
    },
    _applySpecificFont: function(font, oldFont, name) {
      if (name === "labelFont") {
        this.__label.setFont(font);
      } else if (name === "inputFont") {
        this.__input.setFont(font);
      }
    },
    _applyEditable: function(isEditable) {
      if (isEditable) {
        this.__label.addState("editable");
      } else {
        this.__label.removeState("editable");
      }
    }
  }
});
