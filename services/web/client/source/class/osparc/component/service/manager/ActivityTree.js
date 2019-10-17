/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * This is a table display the status of running services in real time. Simulates, in some cases, the behavior of a tree.
 * Has sorting and resizing capabilities, and its UI changes depending on its display mode, that changes depending on the activated type of sorting.
 * WiP
 */
qx.Class.define("osparc.component.service.manager.ActivityTree", {
  extend: qx.ui.treevirtual.TreeVirtual,

  /**
   * Constructor sets the model and general look.
   */
  construct: function() {
    this.base(arguments, [
      "Node",
      "Service",
      "Status",
      "CPU usage",
      "GPU usage"
    ], {
      treeDataCellRenderer: new qx.ui.treevirtual.SimpleTreeDataCellRenderer().set({
        useTreeLines: false
      })
    });
    this.set({
      decorator: "no-border",
      padding: 0
    });
  }
});
