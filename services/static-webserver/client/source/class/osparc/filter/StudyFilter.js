/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.filter.StudyFilter", {
  extend: osparc.filter.TagsFilter,

  /**
   * Constructor for StudyFilter simply calls its parent constructor, passing an appropriate label name.
   *
   * @extends osparc.filter.TagsFilter
   */
  construct: function(filterId, filterGroupId) {
    this.base(arguments, this.tr("Studies"), filterId, filterGroupId);
  },

  members: {
    /**
     * Builds the menu from a list of studies
     * @param {Array} studies List of studies
     */
    buildMenu: function(studies) {
      studies.forEach(study => this._addOption(study.name));
    }
  }
});
