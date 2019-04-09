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
 * This is the controller for Workbench filters.
 */
qx.Class.define("qxapp.component.filter.WorkbenchFilterController", {
  extend: qxapp.component.filter.FilterController,
  type: "singleton",

  construct: function(groupId) {
    this.base(arguments, "workbench");
  }
});
