/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * This is a similar widget to the virtual combo box that changes the behavior of opening the search view
 * and filters the available results depending on what is written in the input.
 * WiP
 */
qx.Class.define("osparc.ui.form.AutocompleteField", {
  extend: qx.ui.form.VirtualComboBox,

  /**
   * Constructor for the autocomplete field just takes an optional parameter with an array of possible values for its menu.
   * @param {Array} [data] Model with the data that will be shown in the menu.
   */
  construct: function(data) {
    this.base(arguments, data);
    this.__textfield = this.getChildControl("textfield");
    this.__attachEventHandlers();
  },

  members: {
    __textfield: null,

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
