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
 * Base class for GUI filters. Stores the filter id and group id and implements common filter operations
 * like dispatching changes.
 */
qx.Class.define("qxapp.component.filter.UIFilter", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function(filterId, groupId) {
    this.base(arguments);
    this.__filterId = filterId;
    this.__groupId = groupId;

    qxapp.component.filter.UIFilterController.getInstance().registerFilter(this.__filterId, this.__groupId);
  },

  members: {
    __filterId: null,
    __groupId: null,
    __capitalizeFn: qxapp.utils.Utils.capitalize,

    __getMessageName: function(suffix = "filter") {
      return this.__capitalizeFn(this.__filterId, this.__groupId, suffix);
    },

    _filterChange: function(data) {
      const msgData = {
        groupId: this.__groupId,
        filterId: this.__filterId,
        data
      };
      qx.event.message.Bus.getInstance().dispatchByName(this.__getMessageName(), msgData);
    }
  }
});
