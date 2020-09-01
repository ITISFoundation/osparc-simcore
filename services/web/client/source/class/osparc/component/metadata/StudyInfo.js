/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 *  Widget placed in the Study Editor that contains the StudyDetails of the given study.
 * and a button that opens a the StudyDetailsEditor.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const studyInfo = new osparc.component.metadata.StudyInfo(study);
 *    this.add(studyInfo);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.StudyInfo", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {Object|osparc.data.model.Study} Study (metadata)
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: 5,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.__study = study;

    this._add(this.__getMoreInfoMenuButton());
    const windowWidth = 400;
    this._add(new osparc.component.metadata.StudyDetails(study, windowWidth));
  },

  members: {
    __study: null,

    __getMoreInfoMenuButton: function() {
      const moreInfoButton = new qx.ui.form.Button(this.tr("More Info")).set({
        icon: "@FontAwesome5Solid/external-link-alt/16",
        allowGrowX: false
      });

      moreInfoButton.addListener("execute", function() {
        this.__createStudyDetailsEditor();
      }, this);
      return moreInfoButton;
    },

    __createStudyDetailsEditor: function() {
      const width = 500;
      const height = 500;
      const title = this.tr("Study Details Editor");
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(this.__study.serializeStudy(), false, width);
      studyDetails.showOpenButton(false);
      const win = osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
        qx.event.message.Bus.getInstance().dispatchByName("updateStudy", this.__study.serializeStudy());
      studyDetails.addListener("updateStudy", () => {
        win.close();
      });
    }
  }
});
