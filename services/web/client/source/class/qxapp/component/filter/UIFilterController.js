/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * GUI filter controller. Stores the state of all filters and dispatches it when it changes.
 */
qx.Class.define("qxapp.component.filter.UIFilterController", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
  },

  statics: {
    registerFilter: function(filterId) {
      this.getInstance().registerFilter(filterId);
    },
  },

  members: {
    __state: {},
    __capitalizeFn: qxapp.utils.Utils.capitalize,

    /**
     * Function called by the base filter class to register a filter when created, to register it.
     *
     * @param {string} filterId Group-unique id of the filter that will be registered.
     * @param {*} groupId Group id for the filter to be registered to.
     */
    registerFilter: function(filterId, groupId) {
      qx.event.message.Bus.getInstance().subscribe(this.__getInputMessageName(filterId, groupId), this.__subscriber, this);
    },

    __getInputMessageName: function(filterId, groupId, suffix = "filter") {
      return this.__capitalizeFn(filterId, groupId, suffix);
    },

    __getOutputMessageName: function(groupId, suffix = "filter") {
      return this.__capitalizeFn(groupId, suffix);
    },

    __subscriber: function(msg) {
      // Update state
      const { groupId, filterId, data } = msg.getData();
      this.__state[groupId] = this.__state[groupId] || {};
      this.__state[groupId][filterId] = data;
      // Dispatch relevant message
      qx.event.message.Bus.getInstance().dispatchByName(this.__getOutputMessageName(groupId), this.__state[groupId]);
    }
  }
});
