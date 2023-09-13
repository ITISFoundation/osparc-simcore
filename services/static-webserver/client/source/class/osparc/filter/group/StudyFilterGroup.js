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
qx.Class.define("osparc.filter.group.StudyFilterGroup", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor takes the desired filterGroupId for the filters group.
   * @param {String} filterGroupId Group id of the filter
   */
  construct: function(filterGroupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(5));

    this.__textFilter = new osparc.filter.TextFilter("text", filterGroupId);
    this.__textFilter.getChildControl("textfield").setFont("text-14");
    osparc.utils.Utils.setIdToWidget(this.__textFilter, "studyFiltersTextFld");
    this._add(this.__textFilter);

    this.__tagsFilter = new osparc.filter.UserTagsFilter("tags", filterGroupId).set({
      visibility: osparc.data.Permissions.getInstance().canDo("study.tag") ? "visible" : "excluded"
    });
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
