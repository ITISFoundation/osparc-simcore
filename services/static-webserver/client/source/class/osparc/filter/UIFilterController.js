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
 * GUI filter controller. Stores the state of all grouped filters and dispatches it when they trigger a change.
 */
qx.Class.define("osparc.filter.UIFilterController", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
  },

  statics: {
    registerFilter: function(filterId) {
      this.getInstance().registerFilter(filterId);
    },
    registerContainer: function(containerId, container) {
      this.getInstance().registerFilterContainer(containerId, container);
    },
    resetGroup: function(filterGroupId) {
      this.getInstance().resetGroup(filterGroupId);
    },
    setContainerVisibility: function(containerId, visibility) {
      this.getInstance().setFilterContainerVisibility(containerId, visibility);
    },
    dispatch: function(filterGroupId) {
      this.getInstance().dispatch(filterGroupId);
    }
  },

  members: {
    __state: null,
    __filters: null,
    __filterContainers: null,

    /**
     * Function called by the base filter class to register a filter when after creating it.
     *
     * @param {osparc.filter.UIFilter} filter The filter to be registered.
     */
    registerFilter: function(filter) {
      const filterId = filter.getFilterId();
      const filterGroupId = filter.getFilterGroupId();
      // Store filter reference for managing
      this.__filters = this.__filters || {};
      this.__filters[filterGroupId] = this.__filters[filterGroupId] || {};
      this.__filters[filterGroupId][filterId] = filter;
    },

    /**
     * Function that registers a filter container for changing its visibility when required.
     *
     * @param {string} containerId Given id for the container.
     * @param {qx.ui.core.Widget} container Container widget for the filters.
     */
    registerContainer: function(containerId, container) {
      this.__filterContainers = this.__filterContainers || {};
      this.__filterContainers[containerId] = container;
    },

    /**
     * Function that calls the reset functions for all filters in a group.
     *
     * @param {string} filterGroupId Id of the filter group to be reset.
     */
    resetGroup: function(filterGroupId) {
      if (this.__filters[filterGroupId]) {
        for (let filterId in this.__filters[filterGroupId]) {
          this.__filters[filterGroupId][filterId].reset();
        }
      }
    },

    /**
     * Function to set the visibility of a previously registered filter container.
     *
     * @param {string} containerId Id of the container to change the visibility.
     * @param {string} visibility New visibility setting for the container.
     */
    setContainerVisibility: function(containerId, visibility) {
      if (this.__filterContainers[containerId]) {
        this.__filterContainers[containerId].setVisibility(visibility);
      }
    },

    __getInputMessageName: function(filterId, filterGroupId, suffix = "filter") {
      return osparc.utils.Utils.capitalize(filterId, filterGroupId, suffix);
    },

    __getOutputMessageName: function(filterGroupId, suffix = "filter") {
      return osparc.utils.Utils.capitalize(filterGroupId, suffix);
    },

    /**
     * Function called when a filter state changes and it wants to publish those changes to trigger the filtering.
     *
     * @param {Object} filterData Mandatory data coming from the filter.
     * @param {String} filterData.filterGroupId Group id of the filter that changed.
     * @param {String} filterData.filterId Filter id of the filter that changed.
     * @param {Object} filterData.data Data contained by the filter.
     */
    publish: function(filterData) {
      // Update state
      const {
        filterGroupId,
        filterId,
        data
      } = filterData;
      this.__state = this.__state || {};
      this.__state[filterGroupId] = this.__state[filterGroupId] || {};
      this.__state[filterGroupId][filterId] = data;
      // Dispatch relevant message
      this.dispatch(filterGroupId);
    },

    /**
     * This function actually dispatches the data for a filter group to apply filtering. It gets called
     * whenever a filter changes or can also be programmatically called.
     *
     * @param {String} filterGroupId Id of the filtering group whose data needs to be dispatched.
     */
    dispatch: function(filterGroupId) {
      if (this.__state && this.__state[filterGroupId]) {
        qx.event.message.Bus.getInstance().dispatchByName(this.__getOutputMessageName(filterGroupId), this.__state[filterGroupId]);
      }
    }
  }
});
