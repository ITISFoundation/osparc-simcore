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

    this._setLayout(new qx.ui.layout.HBox().set({
      alignY: "middle"
    }));

    this.__renderLayout();

    if (value) {
      this.setValue(value);
    }

    this.__loadingIcon = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/12");
    this.__loadingIcon.getContentElement().addClass("rotate");
  },

  events: {
    "editValue": "qx.event.type.Data"
  },

  statics: {
    MODES: {
      DISPLAY: "display",
      EDIT: "edit"
    }
  },

  properties: {
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
    __labelWidth: null,
    __loadingIcon: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "text":
          control = new qx.ui.basic.Label().set({
            appearance: "editlabel-label"
          });
          this.bind("value", control, "value");
          if (this.isEditable()) {
            control.addState("editable");
          }
          control.addListener("pointerover", () => control.addState("hovered"), this);
          control.addListener("pointerout", () => control.removeState("hovered"), this);
          control.addListener("tap", () => this.setMode(this.isEditable() ? this.self().MODES.EDIT : this.self().modes.DISPLAY), this);
          this._add(control);
          break;
        case "input":
          control = new qx.ui.form.TextField(this.getValue()).set({
            appearance: "editlabel-input"
          });
          control.addListener("focusout", () => this.setMode(this.self().MODES.DISPLAY), this);
          control.addListener("focus", () => control.selectAllText(), this);
          control.addListener("changeValue", evt => {
            this.setMode(this.self().MODES.DISPLAY);
            this.fireDataEvent("editValue", evt.getData());
          }, this);
          control.addListener("keydown", e => {
            if (e.getKeyIdentifier() === "Enter") {
              this.setMode(this.self().MODES.DISPLAY);
            }
          }, this);
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    /**
     * This method takes charge of rendering the widget. It relies on the property mode
     * to render the correct version of the widget.
     */
    __renderLayout: function() {
      const label = this.getChildControl("text");
      const input = this.getChildControl("input")
      switch (this.getMode()) {
        case this.self().MODES.EDIT:
          input.show();
          label.exclude();
          if (this.__labelWidth) {
            input.setWidth(this.__labelWidth);
          }
          input.focus();
          label.removeState("hovered");
          break;
        default:
          label.show();
          input.exclude();
      }
    },

    _applyMode: function(mode) {
      if (mode === this.self().MODES.EDIT) {
        this.__labelWidth = this.getChildControl("text").getSizeHint().width;
      }
      this.__renderLayout();
    },

    _applyFetching: function(isFetching) {
      const label = this.getChildControl("text");
      if (isFetching) {
        label.setEnabled(false);
        this._add(this.__loadingIcon);
      } else {
        label.setEnabled(true);
        this._remove(this.__loadingIcon);
      }
    },

    _applyValue: function(value) {
      this.setMode(this.self().MODES.DISPLAY);
      this.getChildControl("input").setValue(value);
    },

    _applySpecificFont: function(font, oldFont, name) {
      if (name === "labelFont") {
        this.getChildControl("text").setFont(font);
      } else if (name === "inputFont") {
        this.getChildControl("input").setFont(font);
      }
    },

    _applyEditable: function(isEditable) {
      const label = this.getChildControl("text");
      if (isEditable) {
        label.addState("editable");
      } else {
        label.removeState("editable");
      }
    }
  }
});
