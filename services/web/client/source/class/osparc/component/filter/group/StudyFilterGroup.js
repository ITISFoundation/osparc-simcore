/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Widget that contains the study filters.
 * Currently: Text filtering and tags filtering.
 */
qx.Class.define("osparc.component.filter.group.StudyFilterGroup", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor takes the desired groupId for the filters group.
   * @param {String} groupId Group id of the filter
   */
  construct: function(groupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this.__textFilter = new osparc.component.filter.TextFilter("text", groupId);
    osparc.utils.Utils.setIdToWidget(this.__textFilter, "studyFiltersTextFld");
    this.__tagsFilter = new osparc.component.filter.UserTagsFilter("tags", groupId);
    this._add(this.__textFilter);
    this._add(this.__tagsFilter);
  },

  members: {
    __textFilter: null,
    __tagsFilter: null,

    /**
     * Resets the text and active tags.
     */
    reset: function() {
      this.__textFilter.reset();
      this.__tagsFilter.reset();
    },

    /**
     * Returns the text filter widget.
     */
    getTextFilter: function() {
      return this.__textFilter;
    }
  }
});
