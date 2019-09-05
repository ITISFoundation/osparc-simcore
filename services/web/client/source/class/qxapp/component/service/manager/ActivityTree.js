/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.service.manager.ActivityTree", {
  extend: qx.ui.treevirtual.TreeVirtual,

  construct: function() {
    this.base(arguments,
    [
      "Node",
      "Service",
      "Status",
      "CPU usage",
      "GPU usage"
    ], {
      treeDataCellRenderer: new qx.ui.treevirtual.SimpleTreeDataCellRenderer().set({
        excludeFirstLevelTreeLines: true,
        useTreeLines: false
      })
    });
    this.set({
      decorator: "no-border",
      padding: 0
    });
  }
});
