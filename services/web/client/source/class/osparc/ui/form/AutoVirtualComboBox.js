/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.form.AutoVirtualComboBox", {
  extend: qx.ui.form.VirtualComboBox,

  construct: function() {
    this.base(arguments);

    const asTextfield = this.getChildControl("textfield");
    const d = new qx.ui.decoration.Decorator().set({
      width: 0
    });
    asTextfield.setDecorator(d);
    asTextfield.addListener("click", this.__onTextfieldInput, this);
    asTextfield.addListener("input", this.__onTextfieldInput, this);

    this.addListener("changeValue", this.__onChangeValue, this);

    this._createChildControlImpl("dropdown");
  },

  properties: {
    matchAtStart: {
      check: "Boolean",
      init: false
    }
  },

  events : {
    "valueSelected": "qx.event.type.Data"
  },

  members: {
    // overridden from ComboBox.js to not add the button control
    _createChildControlImpl: function(id, hash) {
      let control;
      switch (id) {
        case "button":
          // create the button even though we aren't going to add it, because the parent class
          // is probably full of references to this button and we don't want to break those.
          control = new qx.ui.form.Button();
          control.setFocusable(false);
          control.setKeepActive(true);
          control.addState("inner");
          control.addListener("execute", this.toggle, this);
          // this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    updateDropdownContents: function() {
      const textField = this.getChildControl("textfield");
      const tfVal = textField.getValue() === null ? "" : textField.getValue().trim().toLowerCase();

      // is it the right thing to do to keep replacing the delegate on every keystroke?  We keep using
      // the same function, so in theory, if we could just trigger the delegate, we could avoid replacing
      // the delegate over and over; then again, we only have to compute tfVal once this way, instead
      // of having to compute it for every row in the model.

      // This is a hack -- in order to get the label associated with each object in the data model,
      // we have to use the labelPath; the data object doesn't have a function like data.getLabel().  But
      // if you know the label path (e.g. "foo"), you can find the label string in $$user_foo...  You probably
      // shouldn't be actually referencing that directly, but it works...
      const prop = "$$user_" + this.getLabelPath();

      const that = this;
      this.setDelegate({
        filter: function(data) {
          if (tfVal === "") {
            return true;
          }
          if (that.getMatchAtStart()) {
            return data[prop].trim().toLowerCase().indexOf(tfVal) === 0;
          }
          return data[prop].trim().toLowerCase().indexOf(tfVal) >= 0;
        }
      });
    },

    __onTextfieldInput: function(e) {
      this.open();
      this.updateDropdownContents();
    },

    __onChangeValue: function(e) {
      if (e.getData() === null) {
        return;
      }
      const newval = e.getData().trim().toLowerCase();

      const model = this.getModel();

      // see note above about hacking by using the $$user_FOO property directly
      const prop = "$$user_" + this.getLabelPath();
      for (let i = 0; i < model.length; i++) {
        const data = model.getItem(i);

        if (data[prop].trim().toLowerCase() == newval) {
          this.fireDataEvent("valueSelected", data);
          return;
        }
      }
    }
  }
});
