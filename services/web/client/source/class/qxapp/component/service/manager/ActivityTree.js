/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.service.manager.ActivityTree", {
  extend: qx.ui.table.Table,

  construct: function() {
    this.__model = new qx.ui.table.model.Simple();
    this.__model.setColumns([
      "Node",
      "Service",
      "Status",
      "CPU usage",
      "GPU usage"
    ]);
    this.base(arguments, this.__model);
  }
});
