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

  members:{
    /**
     * Subscriber function for incoming messages.
     *
     * @param {qx.event.message.Message} msg Message dispatched.
     */
    _subscriber: function(msg) {
      if (this._shouldReactToFilter(msg.getData()) && this._shouldFilterOut(msg.getData())) {
        this._filterOut();
      } else {
        this._removeFilter();
      }
    }
  }
});
