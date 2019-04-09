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
 * Common functions for all elements that can be filtered
 */
qx.Mixin.define("qxapp.component.filter.MFiltrable", {
  members: {
    /**
     * Used to subscribe the element to a filter group.
     *
     * @param {String} groupId Id of the filter group to subscribe to.
     */
    _subscribeToFilterGroup: function(groupId) {
      qx.event.message.Bus.getInstance().subscribe(groupId, this.__subscriber, this);
    },
    /**
     * Subscriber function for incoming messages.
     *
     * @param {qx.event.message.Message} msg Message dispatched.
     */
    __subscriber: function(msg) {
      if (this._shouldReactToFilter(msg.getData(), msg) && this._shouldFilterOut(msg.getData(), msg)) {
        this._filterOut(msg.getData(), msg);
      } else {
        this._unfilter(msg.getData(), msg);
      }
    }
  }
});
