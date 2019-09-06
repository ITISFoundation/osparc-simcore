/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.ui.form.AutocompleteField", {
  extend: qx.ui.form.VirtualComboBox,

  construct: function(data) {
    this.base(arguments, data);
    this.__textfield = this.getChildControl("textfield");
    this.__attachEventHandlers();
  },

  members: {
    __textfield: null,
    __dropdown: null,
    __attachEventHandlers: function() {
      this.__textfield.setLiveUpdate(true);
      this.__textfield.addListener("changeValue", e => {
        if (e.getData() && e.getData().length) {
          this.open();
        } else {
          this.close();
        }
      }, this);
      this.__textfield.addListener("focusout", e => this.close(), this);
    }
  }
});
