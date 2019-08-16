/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("qxapp.component.metadata.StudyDetailsWindow", {
  extend: qx.ui.window.Window,
  construct: function(study) {
    this.base(arguments, this.tr("Study information") + " · " + study.getName());

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

    const thumbnailWidth = (windowWidth - 250)/1.67;
    const studyDetails = new qxapp.component.metadata.StudyDetails(study, thumbnailWidth);
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
