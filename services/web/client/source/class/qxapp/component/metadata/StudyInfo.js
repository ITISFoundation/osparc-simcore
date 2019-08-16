/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Widget that contains the StudyDetails of the given study metadata.
 *
 * It also provides a button that opens a window with the same information.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const serviceInfo = new qxapp.component.metadata.ServiceInfo(selectedService);
 *    this.add(serviceInfo);
 * </pre>
 */

qx.Class.define("qxapp.component.metadata.StudyInfo", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {Object|qxapp.data.model.Study} Study (metadata)
    */
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
        const win = new qxapp.component.metadata.StudyDetailsWindow(this.__study);
        win.center();
        win.open();
      }, this);
      return expandButton;
    }
  }
});
