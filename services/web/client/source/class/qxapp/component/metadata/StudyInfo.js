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

    this.set({
      padding: 5,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.__study = study;

    this._add(this.__createExpandButton());
    const windowWidth = 500;
    const thumbnailWidth = (windowWidth - 250)/1.67;
    this._add(new qxapp.component.metadata.StudyDetails(study, thumbnailWidth), {
      flex: 1
    });
  },

  members: {
    __study: null,

    __createExpandButton: function() {
      const expandButton = new qx.ui.form.Button().set({
        label: this.tr("Show all"),
        icon: "@FontAwesome5Solid/external-link-alt/16",
        allowGrowX: false
      });
      expandButton.addListener("execute", function() {
        const windowWidth = 700;
        const windowHeight = 700;
        const thumbnailWidth = (windowWidth - 250)/1.67;
        const studyDetails = new qxapp.component.metadata.StudyDetails(this.__study, thumbnailWidth);
        const scroll = new qx.ui.container.Scroll().set({
          height: windowHeight
        });
        scroll.add(studyDetails);

        const win = new qx.ui.window.Window(this.tr("Study information")).set({
          layout: new qx.ui.layout.Grow(),
          contentPadding: 10,
          showMinimize: false,
          modal: true,
          width: windowWidth,
          height: 700
        });
        win.add(scroll);

        win.center();
        win.open();
      }, this);
      return expandButton;
    }
  }
});
