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

qx.Class.define("osparc.ui.form.ChipsField", {
  extend: qx.ui.form.AbstractField,

  construct: function(values) {
    this.base(arguments, new qx.ui.layout.Canvas());

    this.__chips = [];
    this.__ignoreComboboxChangeValue = false;

    this.__init();

    if (typeof values !== "undefined") {
      this.setChips(values);
    }
  },

  events: {
    "valueSelected": "qx.event.type.Data",
    "changeValue" : "qx.event.type.Data"
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _forwardStates: {
      focused : true,
      invalid : true
    },

    __chips: null,
    __combobox: null,
    __ignoreComboboxChangeValue: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "chip-board": {
          const l = new qx.ui.layout.Flow().set({
            spacingX: 4,
            spacingY: 4
          });

          control = new qx.ui.container.Composite(l);
          this._add(control, {
            left: 4,
            top: 4,
            right: 4,
            bottom: 4
          });
          control.addListener("click", e => {
            if (this.__combobox !== null) {
              this.__combobox.focus();
            }
          }, this);
          break;
        }
        case "combobox": {
          control = new osparc.ui.form.AutoVirtualComboBox();
          control.addListener("click", e => {
            // we need this in order to keep a click on the combobox from triggering the click event
            // on the chipboard, which would put the focus into the combobox, closing the popup!
            e.stopPropagation();
          });

          control.addListener("valueSelected", this.__onComboboxValueSelected, this);

          control.set({
            width: 200
          });

          const d = new qx.ui.decoration.Decorator().set({
            width: 0
          });
          control.setDecorator(d);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __init: function() {
      this._removeAll();

      const d = new qx.ui.decoration.Decorator().set({
        color: "#000",
        width: 1
      });
      this.setDecorator(d);

      const chipBoard = this.getChildControl("chip-board");
      if (this.__combobox !== null) {
        chipBoard.remove(this.__combobox);
      }

      const combobox = this.__combobox = this._createChildControl("combobox");
      chipBoard.add(combobox);
    },

    setChips: function(values) {
      const chipBoard = this.getChildControl("chip-board");
      chipBoard.removeAll();

      this.__chips = [];
      values.forEach(value => {
        const c = this.__createChip(value.data, value.caption);
        this.__chips.push(c);
        chipBoard.add(c);
      });

      if (this.__combobox !== null) {
        chipBoard.add(this.__combobox);
      }
    },

    addChip: function(data, caption) {
      const chipBoard = this.getChildControl("chip-board");

      const strData = JSON.stringify(data);
      this.__chips.forEach(chip => {
        if (JSON.stringify(chip.getData()) === strData) {
          this.cancelChipAdd();
          return;
        }
      });

      if (this.__combobox !== null) {
        chipBoard.remove(this.__combobox);
      }

      const c = this.__createChip(data, caption);
      this.__chips.push(c);
      chipBoard.add(c);

      if (this.__combobox !== null) {
        this.__ignoreComboboxChangeValue = true;
        this.__combobox.setValue("");
        this.__combobox.updateDropdownContents();
        chipBoard.add(this.__combobox);
        this.__ignoreComboboxChangeValue = false;
      }
    },

    cancelChipAdd: function() {
      this.__ignoreComboboxChangeValue = true;
      this.__combobox.setValue("");
      this.__combobox.updateDropdownContents();
      this.__ignoreComboboxChangeValue = false;
    },

    setSuggestions: function(suggestions, labelPath) {
      const model = qx.data.marshal.Json.createModel(suggestions);

      this.__combobox.setLabelPath(labelPath);
      this.__combobox.setModel(model);
    },

    __onComboboxValueSelected: function(e) {
      if (this.__ignoreComboboxChangeValue) {
        return;
      }

      this.fireDataEvent("valueSelected", e.getData());
    },

    __removeChip: function(c) {
      const chipBoard = this.getChildControl("chip-board");
      chipBoard.remove(c);

      const newChips = [];
      this.__chips.forEach(chip => {
        if (chip !== c) {
          newChips.push(chip);
        }
      });

      this.__chips = newChips;
    },

    __createChip: function(data, caption) {
      const c = new osparc.ui.basic.ChipClose(data, caption);
      c.addListener("deleteClicked", () => {
        this.__removeChip(c);
      }, this);

      return c;
    },


    /**
     * @param value {Array} Array of Strings
     */
    setValue: function(value) {
      if (Array.isArray(value)) {
        this.setChips(value);
      } else {
        this.setChips([value]);
      }
    },


    /**
     * @return {Array} Array of Strings
     */
    getValue: function() {
      if (this.__chips.length) {
        return this.__chips;
      }
      return "";
    },

    resetValue: function() {
      this.__init();
    }
  }
});
