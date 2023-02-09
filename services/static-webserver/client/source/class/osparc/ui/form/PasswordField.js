/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.form.PasswordField", {
  extend : qx.ui.core.Widget,
  include : [
    qx.ui.form.MForm
  ],
  implement : [
    qx.ui.form.IStringForm,
    qx.ui.form.IForm
  ],

  construct: function() {
    this.base(arguments);

    this.set({
      padding: 0
    });

    // set the layout
    const layout = new qx.ui.layout.HBox();
    this._setLayout(layout);
    layout.setAlignY("middle");

    // password field
    const passwordField = this._createChildControl("passwordField");
    this._createChildControl("eyeButton");

    this.__focusedBorder(false);

    // forward the focusin and focusout events to the passwordField. The passwordField
    // is not focusable so the events need to be forwarded manually.
    this.addListener("focusin", () => passwordField.fireNonBubblingEvent("focusin", qx.event.type.Focus), this);
    this.addListener("focusout", () => {
      this.__focusedBorder(false);
      passwordField.fireNonBubblingEvent("focusout", qx.event.type.Focus);
    }, this);
  },

  events: {
    "changeValue" : "qx.event.type.Data"
  },

  properties: {
    placeholder: {
      check: "String",
      nullable: true,
      apply: "_applyPlaceholder"
    },

    // overridden
    appearance: {
      refine: true,
      init: "textfield"
    },

    // overridden
    focusable: {
      refine: true,
      init: true
    },

    // overridden
    width: {
      refine: true,
      init: 120
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    /**
     * @lint ignoreReferenceField(_forwardStates)
     */
    _forwardStates: {
      focused : true,
      invalid : true
    },

    setValue: function(value) {
      this.getChildControl("passwordField").setValue(value);
    },

    resetValue: function() {
      this.getChildControl("passwordField").resetValue();
    },

    getValue: function() {
      return this.getChildControl("passwordField").getValue();
    },

    _applyPlaceholder : function(value) {
      this.getChildControl("passwordField").setPlaceholder(value);
    },

    // overridden
    _createChildControlImpl : function(id) {
      let control;
      switch (id) {
        case "passwordField":
          control = new qx.ui.form.PasswordField();
          control.getContentElement().setStyles({
            "border-bottom-width": "0px"
          });
          control.addListener("changeValue", () => this.fireDataEvent("changeValue", control.getValue()), this);
          this._add(control, {
            flex: 1
          });
          break;
        case "eyeButton":
          control = new qx.ui.form.ToggleButton().set({
            maxHeight: 18,
            width: 22,
            padding: 0,
            paddingRight: 4,
            icon: "@FontAwesome5Solid/eye/10",
            backgroundColor: "transparent"
          });
          control.addListener("tap", this.__toggleEye, this);
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __toggleEye: function() {
      const passwordField = this.getChildControl("passwordField");
      if (passwordField.getContentElement() && passwordField.getContentElement().getDomElement()) {
        const domEl = passwordField.getContentElement().getDomElement();
        const eyeButton = this.getChildControl("eyeButton");
        if (eyeButton.getValue()) {
          // show
          domEl.setAttribute("type", "text");
          eyeButton.setIcon("@FontAwesome5Solid/eye-slash/10");
        } else {
          // hide
          domEl.setAttribute("type", "password");
          eyeButton.setIcon("@FontAwesome5Solid/eye/10");
        }
      }
    },

    isEmpty: function() {
      const value = this.getChildControl("passwordField").getValue();
      return value == null || value == "";
    },

    // overridden
    focus: function() {
      this.base(arguments);
      this.getChildControl("passwordField").getFocusElement().focus();
      this.__focusedBorder(true);
    },

    // overridden
    tabFocus: function() {
      const field = this.getChildControl("passwordField");
      field.getFocusElement().focus();
      field.selectAllText();
      this.__focusedBorder(true);
    },

    __focusedBorder: function(focused = false) {
      this.getContentElement().setStyles({
        "border-bottom-width": focused ? "2px" : "1px",
        "border-color": "text"
      });
    }
  }
});
