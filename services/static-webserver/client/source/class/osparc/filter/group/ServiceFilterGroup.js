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
 * Widget that contains the service filters.
 */
qx.Class.define("osparc.filter.group.ServiceFilterGroup", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor takes the desired filterGroupId for the filters group.
   * @param {String} filterGroupId Group id of the filter
   */
  construct: function(filterGroupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(5));
    this.__filterGroupId = filterGroupId;
    const textFilter = this.__textFilter = new osparc.filter.TextFilter("text", filterGroupId);
    osparc.utils.Utils.setIdToWidget(textFilter, "serviceFiltersTextFld");
    const tagsFilter = this.__tagsFilter = new osparc.filter.NodeTypeFilter("tags", filterGroupId);
    this._add(textFilter);
    this._add(tagsFilter);
  },

  members: {
    __textFilter: null,
    __tagsFilter: null,
    __filterGroupId: null,

    /**
     * Resets the text and active tags.
     */
    reset: function() {
      this.__textFilter.reset();
      this.__tagsFilter.reset();
    },

    /**
     * Programmatically triggers filtering again.
     */
    dispatch: function() {
      osparc.filter.UIFilterController.dispatch(this.__filterGroupId);
    },

    /**
     * Returns the text filter widget.
     */
    getTextFilter: function() {
      return this.__textFilter;
    },

    getTagsFilter: function() {
      return this.__tagsFilter;
    }
  }
});
