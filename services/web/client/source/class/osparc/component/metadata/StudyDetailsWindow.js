/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Window that contains the StudyDetails of the given study metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const win = new osparc.component.metadata.StudyDetailsWindow(study);
 *   win.center();
 *   win.open();
 * </pre>
 */

qx.Class.define("osparc.component.metadata.StudyDetailsWindow", {
  extend: qx.ui.window.Window,

  /**
    * @param study {Object|osparc.data.model.Study} Study (metadata)
    */
  construct: function(study) {
    this.base(arguments, this.tr("Study information") + " · " + study.getName());

    const windowWidth = 700;
    const windowHeight = 800;
    this.set({
      layout: new qx.ui.layout.Grow(),
      autoDestroy: true,
      contentPadding: 10,
      showMinimize: false,
      resizable: true,
      modal: true,
      width: windowWidth,
      height: windowHeight
    });

    const studyDetails = new osparc.component.metadata.StudyDetails(study, windowWidth);
    const scroll = new qx.ui.container.Scroll().set({
      height: windowHeight
    });
    scroll.add(studyDetails);
    this.add(scroll);
  },

  properties: {
    appearance: {
      refine: true,
      init: "info-service-window"
    }
  }
});
