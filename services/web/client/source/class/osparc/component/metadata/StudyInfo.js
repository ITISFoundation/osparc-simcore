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

  construct: function() {
    this.base(arguments);

    this.set({
      padding: 5,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this._add(this.__getMoreInfoMenuButton());
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "_applyStudy",
      nullable: false
    }
  },

  members: {
    __studyDetails: null,

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

    _applyStudy: function(study) {
      if (this.__studyDetails) {
        this._remove(this.__studyDetails);
      }

      const windowWidth = 400;
      const studyDetails = this.__studyDetails = new osparc.component.metadata.StudyDetails(study, windowWidth);
      this._add(studyDetails);
    },

    __createStudyDetailsEditor: function() {
      const width = 500;
      const height = 500;
      const title = this.tr("Study Details Editor");
      const studyDetailsEditor = new osparc.component.metadata.StudyDetailsEditor(this.getStudy().serialize(), false, width);
      studyDetailsEditor.showOpenButton(false);
      const win = osparc.ui.window.Window.popUpInWindow(studyDetailsEditor, title, width, height);
      studyDetailsEditor.addListener("updateStudy", e => {
        const newStudyData = e.getData();
        this.getStudy().set({
          name: newStudyData.name,
          description: newStudyData.description,
          thumbnail: newStudyData.thumbnail
        });
        qx.event.message.Bus.getInstance().dispatchByName("updateStudy", newStudyData.uuid);
        win.close();
      });
    }
  }
});
