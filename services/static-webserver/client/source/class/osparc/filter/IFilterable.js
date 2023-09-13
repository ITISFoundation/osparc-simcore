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
 * Defines the methods all UI filterable elements should implement.
 */
qx.Interface.define("osparc.filter.IFilterable", {
  members:{
    /**
     * Function in charge of setting the element to a filtered state.
     * It will usually hide it or decrease its opacity, but it could also trigger some other UI changes.
     *
     * @param {Object?} data The data contained in the message.
     * @param {qx.event.message.Message?} msg Incoming message containing the data.
     */
    _filter: function(data, msg) {
      this.assertArgumentsCount(arguments, 0, 2);
      if (msg) {
        this.assertInstance(msg, qx.event.message.Message);
      }
    },

    /**
     * Function in charge of removing the filtered state from the element.
     * It will usually make it visible again, but it could also trigger some other UI changes.
     *
     * @param {Object?} data The data contained in the message.
     * @param {qx.event.message.Message?} msg Incoming message containing the data.
     */
    _unfilter: function(data, msg) {
      this.assertArgumentsCount(arguments, 0, 2);
      if (msg) {
        this.assertInstance(msg, qx.event.message.Message);
      }
    },

    /**
     * Function deciding if the element should react to a filter.
     * It serves as a pre-check before the actual decision of being filtered out or not is made.
     * For example, an element could decide not to react to a text search filter if the length of the text to search is shorter than n characters.
     * It should check the data for all filter ids and return true if it should react to any of them.
     *
     * @param {Object} data The data contained in the message.
     * @param {qx.event.message.Message?} msg Incoming message containing the data.
     * @return {Boolean} True or false depending on whether the element should take any filter into account.
     */
    _shouldReactToFilter: function(data, msg) {
      this.assertArgumentsCount(arguments, 1, 2);
      if (msg) {
        this.assertInstance(msg, qx.event.message.Message);
      }
    },

    /**
     * Function deciding if the element should be filtered out or not from the interface.
     * It should check the data for all filter ids of its group and return true if the element qualifies to be filtered out.
     *
     * @param {Object} data The data contained in the message.
     * @param {qx.event.message.Message?} msg Incoming message containing the data.
     * @return {Boolean} True or false depending on whether the element should be switched to a filtered state.
     */
    _shouldApplyFilter: function(data, msg) {
      this.assertArgumentsCount(arguments, 1, 2);
      if (msg) {
        this.assertInstance(msg, qx.event.message.Message);
      }
    }
  }
});
