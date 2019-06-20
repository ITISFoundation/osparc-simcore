/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.metadata.StudyInfo", {
  extend: qx.ui.core.Widget,
  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());
    
    const title = new qx.ui.basic.Label(study.getName()).set({
      font: "title-14",
      rich: true
    });
    this._add(title);

    const description = new qx.ui.basic.Label(study.getDescription()).set({
      rich: true
    });
    this._add(description);

    const extraInfo = this.__createExtraInfo(study);
    const more = new qxapp.desktop.PanelView("More", extraInfo);
    this._add(more);
  },

  members: {
    __createExtraInfo: function(study) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const creationDate = new qx.ui.basic.Label(study.getCreationDate().toString());
      container.add(creationDate);
      return container;
    }
  }
});