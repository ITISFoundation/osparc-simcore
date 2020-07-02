/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Window that contains the ServiceInfo of the given service metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const win = new osparc.component.metadata.ServiceInfoWindow(service);
 *   win.center();
 *   win.open();
 * </pre>
 */

qx.Class.define("osparc.component.metadata.ServiceInfoWindow", {
  extend: qx.ui.window.Window,

  /**
    * @param metadata {Object} Service metadata
    */
  construct: function(metadata) {
    this.base(arguments, this.tr("Service information") + " · " + metadata.name);

    const windowWidth = 700;
    const windowHeight = 800;
    this.set({
      layout: new qx.ui.layout.VBox(10),
      autoDestroy: true,
      contentPadding: 10,
      showMinimize: false,
      resizable: true,
      modal: true,
      width: windowWidth,
      height: windowHeight
    });

    const serviceInfo = this._serviceInfo = new osparc.component.metadata.ServiceInfo(metadata);
    const scroll = new qx.ui.container.Scroll();
    scroll.add(serviceInfo);
    this.add(scroll, {
      flex: 1
    });
  },

  properties: {
    appearance: {
      refine: true,
      init: "info-service-window"
    }
  },

  members: {
    _serviceInfo: null
  }
});
