/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.service.manager.ActivityManager", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.createFiltersBar();
    this.createActivityTree();
    this.createActionsBar();
  },

  members: {
    createFiltersBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const filtersPart = new qx.ui.toolbar.Part();
      toolbar.add(filtersPart);
  
      const nameFilter = new qxapp.component.filter.TextFilter("name", "activityMonitor");
      filtersPart.add(nameFilter);
  
      this._add(toolbar);
    },
  
    createActivityTree: function() {
      const tree = new qx.ui.treevirtual.TreeVirtual([
        "Name",
        "Service",
        "Status",
        "CPU usage",
        "GPU usage"
      ]);
      this._add(tree, {
        flex: 1
      });
    },
  
    createActionsBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const actionsPart = new qx.ui.toolbar.Part();
      toolbar.add(actionsPart);
  
      const runButton = new qx.ui.toolbar.Button(this.tr("Run"), "@FontAwesome5Solid/play/14");
      actionsPart.add(runButton);
  
      const stopButton = new qx.ui.toolbar.Button(this.tr("Stop"), "@FontAwesome5Solid/stop-circle/14");
      actionsPart.add(stopButton);
  
      const infoButton = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info/14");
      actionsPart.add(infoButton);
  
      this._add(toolbar);
    }
  }
});
