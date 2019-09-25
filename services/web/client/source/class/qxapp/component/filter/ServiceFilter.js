/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Filter used for filtering services. Gets the list of services and uses them as possible options for the dropdown.
 */
qx.Class.define("qxapp.component.filter.ServiceFilter", {
  extend: qxapp.component.filter.UIFilter,

  /**
   * Constructor takes the usual parameters, like the rest of UI filters.
   * @param {String} filterId Id of the filter. Must be unique among the other filters in the group
   * @param {String} groupId Group id for the group of filters
   */
  construct: function(filterId, groupId) {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.Canvas());

    this.__autocompleteField = this.getChildControl("autocompletefield").set({
      placeholder: this.tr("Filter by service")
    });

    this.getChildControl("clearbutton");

    const services = qxapp.store.Store.getInstance().getServices();
    const dropdownData = Object.keys(services).map(key => {
      const split = key.split("/");
      return split[split.length-1];
    });
    this.__autocompleteField.setModel(new qx.data.Array(dropdownData));
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
          control = new qxapp.ui.form.AutocompleteField();
          this._add(control);
          break;
        case "clearbutton":
          control = new qxapp.component.form.IconButton("@MaterialIcons/close/12", () => this.reset());
          this._add(control, {
            right: 0,
            bottom: 12
          });
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});
