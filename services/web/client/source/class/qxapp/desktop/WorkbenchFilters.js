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
 * Widget that contains the workbench filters
 */

qx.Class.define("qxapp.desktop.WorkbenchFilters", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this._add(new qxapp.component.filter.TextFilter("text", "workbench"));

    this._add(new qxapp.component.filter.TagsFilter("tags", "workbench"));
  }
});
