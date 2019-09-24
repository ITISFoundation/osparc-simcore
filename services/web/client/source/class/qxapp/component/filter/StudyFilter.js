/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.filter.StudyFilter", {
  extend: qxapp.component.filter.TagsFilter,

  /**
   * Constructor for StudyFilter creates the filter and builds its menu.
   *
   * @extends qxapp.component.filter.TagsFilter
   */
  construct: function(filterId, groupId) {
    this.base(arguments, this.tr("Studies"), filterId, groupId);
  },

  members: {
    buildMenu: function(studies) {
      studies.forEach(study => this._addOption(study.name));
    }
  }
});
