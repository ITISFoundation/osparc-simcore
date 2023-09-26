/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Filter with a dropdown and autocomplete
 */
qx.Class.define("osparc.filter.AutocompleteFilter", {
  extend: osparc.filter.UIFilter,

  /**
   * Constructor takes the usual parameters, like the rest of UI filters.
   * @param {String} filterId Id of the filter. Must be unique among the other filters in the group
   * @param {String} filterGroupId Group id for the group of filters
   */
  construct: function(filterId, filterGroupId) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Canvas());

    this.__autocompleteField = this.getChildControl("autocompletefield");

    this.getChildControl("clearbutton");

    this.__attachEventHandlers();
  },

  properties: {
    appearance: {
      refine: true,
      init: "autocompletefilter"
    }
  },

  members: {
    __autocompleteField: null,

    /**
     * Function that resets the field and dispatches the update.
     */
    reset: function() {
      this.__autocompleteField.resetValue();
      this.__autocompleteField.fireDataEvent("input", "");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "autocompletefield":
          control = new osparc.ui.form.AutocompleteField();
          this._add(control);
          break;
        case "clearbutton":
          control = new osparc.ui.basic.IconButton("@MaterialIcons/close/12", () => this.reset());
          this._add(control, {
            right: 0,
            bottom: 12
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      this.__autocompleteField.addListener("changeValue", e => this._filterChange(e.getData()), this);
    },

    buildMenu: function(menuData) {
      this.__autocompleteField.setModel(new qx.data.Array(menuData));
    }
  }
});
