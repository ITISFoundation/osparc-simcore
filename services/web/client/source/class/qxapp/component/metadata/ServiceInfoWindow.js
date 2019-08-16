/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.metadata.ServiceInfoWindow", {
  extend: qx.ui.window.Window,
  construct: function(metadata) {
    this.base(arguments, this.tr("Service information") + " · " + metadata.name);

    const windowWidth = 700;
    const windowHeight = 800;
    this.set({
      layout: new qx.ui.layout.Grow(),
      contentPadding: 10,
      showMinimize: false,
      resizable: true,
      modal: true,
      width: windowWidth,
      height: windowHeight
    });

    const serviceDetails = new qxapp.component.metadata.ServiceInfo(metadata);
    const scroll = new qx.ui.container.Scroll();
    scroll.add(serviceDetails);
    this.add(scroll);
  },

  properties: {
    appearance: {
      refine: true,
      init: "info-service-window"
    }
  }
});
