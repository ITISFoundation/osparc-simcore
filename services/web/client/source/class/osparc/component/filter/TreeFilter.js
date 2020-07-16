/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.filter.TreeFilter", {
  extend: osparc.component.filter.UIFilter,
  construct: function(filterId, filterGroupId) {
    this.base(arguments, filterId, filterGroupId);
    this._add(new qx.ui.basic.Label("Hello world"));
  }
});
