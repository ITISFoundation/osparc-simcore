/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.form.DateTimeField", {
  extend: qx.ui.core.Widget,
  include: [qx.ui.form.MForm],
  implement: [qx.ui.form.IForm, qx.ui.form.IStringForm],

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    // Date selector
    this.__dateField = new qx.ui.form.DateField();
    this.__dateField.set({
      minimumDate: new Date() // forbid past dates
    });
    this._add(this.__dateField);

    // Hour selector
    this.__hourSpinner = new qx.ui.form.Spinner(0, 12, 23);
    this._add(this.__hourSpinner);

    // Minute selector
    this.__minuteSpinner = new qx.ui.form.Spinner(0, 0, 59);
    this._add(this.__minuteSpinner);

    // Sync changes back to value
    this.__dateField.addListener("changeValue", this.__updateValue, this);
    this.__hourSpinner.addListener("changeValue", this.__updateValue, this);
    this.__minuteSpinner.addListener("changeValue", this.__updateValue, this);
  },

  properties: {
    // The combined Date value
    value: {
      check: "Date",
      nullable: true,
      event: "changeValue",
      apply: "_applyValue"
    }
  },

  members: {
    __dateField: null,
    __hourSpinner: null,
    __minuteSpinner: null,

    _applyValue: function(value, old) {
      if (value) {
        this.__dateField.setValue(value);
        this.__hourSpinner.setValue(value.getHours());
        this.__minuteSpinner.setValue(value.getMinutes());
      } else {
        this.__dateField.resetValue();
        this.__hourSpinner.resetValue();
        this.__minuteSpinner.resetValue();
      }
    },

    __updateValue: function() {
      const date = this.__dateField.getValue();
      if (date) {
        const newDate = new Date(date.getTime());
        newDate.setHours(this.__hourSpinner.getValue());
        newDate.setMinutes(this.__minuteSpinner.getValue());

        const now = new Date();

        // If same day, ensure time is not in the past
        const isToday =
          date.getFullYear() === now.getFullYear() &&
          date.getMonth() === now.getMonth() &&
          date.getDate() === now.getDate();

        if (isToday && newDate < now) {
          // Snap to current time if invalid
          this.__hourSpinner.setValue(now.getHours());
          this.__minuteSpinner.setValue(now.getMinutes());
          this.setValue(now);
        } else {
          this.setValue(newDate);
        }
      } else {
        this.resetValue();
      }
    },

    // Interface methods (IStringForm)
    setValueAsString: function(str) {
      const d = new Date(str);
      if (!isNaN(d.getTime())) {
        this.setValue(d);
      }
    },

    getValueAsString: function() {
      const v = this.getValue();
      return v ? v.toISOString() : "";
    }
  },

  destruct: function() {
    this.__dateField = null;
    this.__hourSpinner = null;
    this.__minuteSpinner = null;
  }
});
