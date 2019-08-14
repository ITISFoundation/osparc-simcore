/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.metadata.ServiceInfoWindow", {
  extend: qx.ui.window.Window,
  construct: function(metadata) {
    this.base(arguments, this.tr("Service information") + " · " + metadata.name);

    this.set({
      layout: new qx.ui.layout.Grow(),
      contentPadding: 0,
      showMinimize: false,
      resizable: false,
      modal: true
    });

    this.add(new osparc.component.metadata.ServiceInfo(metadata));
  },

  properties: {
    appearance: {
      refine: true,
      init: "info-service-window"
    }
  }
});
