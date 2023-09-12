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
 * Base class for GUI filters. Stores the filter id and group id and implements common filter operations
 * like dispatching changes.
 */
qx.Class.define("osparc.filter.UIFilter", {
  extend: qx.ui.core.Widget,
  implement: osparc.filter.IFilter,
  type: "abstract",

  /**
   * Base constructor for UIFilter takes the mandatory ids for the filter and the filter group it belongs to.
   *
   * @param {string} filterId Group-unique id for the filter.
   * @param {string} filterGroupId Unique group id where the filter belongs.
   */
  construct: function(filterId, filterGroupId) {
    this.base(arguments);
    this.set({
      filterId,
      filterGroupId
    });

    osparc.filter.UIFilterController.getInstance().registerFilter(this);
  },

  properties: {
    filterId: {
      nullable: false,
      check: "String"
    },
    filterGroupId: {
      nullable: false,
      check: "String"
    }
  },

  members: {
    /**
     * Function that returns the name of the dispatched message when a filter changes.
     *
     * @param {string} suffix Will be added at the end of the message name to decrease the probability of message name collision.
     */
    _getMessageName: function(suffix = "filter") {
      return osparc.utils.Utils.capitalize(this.getFilterId(), this.getFilterGroupId(), suffix);
    },

    /**
     * Function that should be call whenever the filter wants to send its data to the controller and trigger some filtering.
     *
     * @param {Object} data Raw data coming from the filter.
     */
    _filterChange: function(data) {
      const filterData = {
        filterGroupId: this.getFilterGroupId(),
        filterId: this.getFilterId(),
        data
      };
      osparc.filter.UIFilterController.getInstance().publish(filterData);
    }
  }
});
