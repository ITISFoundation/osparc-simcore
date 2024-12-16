/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * This is a view to display the available services in a flowing fashion. Creates a ServiceButtonGrid button
 * for every service in the model and subscribes it to the filter group.
 */
qx.Class.define("osparc.service.ServiceList", {
  extend: qx.ui.core.Widget,

  /**
   * If the optional parameter is given, the elements will be subscribed to the filter group of the given id.
   *
   * @param {String} [filterGroupId] Id of the filter group the ServiceButtonGrid buttons will be subscribed to.
   */
  construct: function(filterGroupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Flow(5, 5));
    if (filterGroupId) {
      this.__filterGroup = filterGroupId;
    }
  },

  events: {
    "changeSelected": "qx.event.type.Data",
    "serviceAdd": "qx.event.type.Data"
  },

  properties: {
    appearance: {
      refine: true,
      init: "service-browser"
    },
    model: {
      nullable: true,
      check: "qx.data.Array",
      apply: "_applyModel"
    }
  },

  members: {
    __filterGroup: null,

    _applyModel: function(model) {
      this._removeAll();

      this.__serviceListItem = [];
      model.toArray().forEach(service => {
        const item = new osparc.service.ServiceListItem(service);
        if (this.__filterGroup !== null) {
          item.subscribeToFilterGroup(this.__filterGroup);
        }
        this._add(item);
        item.addListener("tap", () => this.__setSelected(item));
        item.addListener("dbltap", () => this.fireDataEvent("serviceAdd", item.getService()), this);
        item.addListener("keypress", e => {
          if (e.getKeyIdentifier() === "Enter") {
            this.fireDataEvent("serviceAdd", item.getService());
          }
        }, this);
      });
    },

    /**
     * Public function to get the currently selected service.
     *
     * @return Returns the model of the selected service or null if selection is empty.
     */
    getSelected: function() {
      const items = this._getChildren();
      for (let i=0; i<items.length; i++) {
        const item = items[i];
        if (item.isVisible() && item.getSelected()) {
          return item.getService();
        }
      }
      return null;
    },

    __setSelected: function(selectedItem) {
      this._getChildren().forEach(item => item.setSelected(item === selectedItem));
      this.fireDataEvent("changeSelected", selectedItem);
    },

    /**
     * Function checking if the selection is empty or not
     *
     * @return True if no item is selected, false if there one or more item selected.
     */
    isSelectionEmpty: function() {
      const selecetedItems = this._getChildren().filter(item => item.getSelected());
      selecetedItems.length === 0;
    },

    /**
     * Function that selects the first visible button.
     */
    selectFirstVisible: function() {
      const items = this._getChildren();
      for (let i=0; i<items.length; i++) {
        const item = items[i];
        if (item.isVisible()) {
          this.__setSelected(item);
          return;
        }
      }
    }
  }
});
