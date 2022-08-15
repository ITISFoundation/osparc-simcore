/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget for creating a template from a study
 * - Creates a copy of study data
 * - Using the ShareWith widget allows to publish the template
 */

qx.Class.define("osparc.component.study.SaveAsTemplate", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__studyDataClone = osparc.data.model.Study.deepCloneStudyObject(studyData);

    this.__buildLayout();
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  members: {
    __studyDataClone: null,
    __shareWith: null,
    __copyWData: null,

    __buildLayout: function() {
      const shareWith = this.__shareWith = new osparc.component.permissions.ShareWith();
      this._add(shareWith, {
        flex: 1
      });

      const publishWithdData = this.__copyWData = new qx.ui.form.CheckBox(this.tr("Publish with data")).set({
        value: true
      });
      this._add(publishWithdData);

      const saveAsTemplateBtn = new osparc.ui.form.FetchButton().set({
        appearance: "strong-button",
        label: this.tr("Publish"),
        allowGrowX: false,
        alignX: "right"
      });
      saveAsTemplateBtn.addListener("execute", () => this.__shareResource(saveAsTemplateBtn), this);
      shareWith.bind("ready", saveAsTemplateBtn, "enabled");
      this._add(saveAsTemplateBtn);
    },

    __shareResource: function(btn) {
      btn.setFetching(true);

      const selectedGroupIDs = this.__shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(gid => {
        this.__studyDataClone["accessRights"][gid] = {
          "read": true,
          "write": false,
          "delete": false
        };
      });

      this.__saveAsTemplate(btn);
    },

    __saveAsTemplate: function(btn) {
      const params = {
        url: {
          "study_id": this.__studyDataClone.uuid,
          "copy_data": this.__copyWData.getValue()
        },
        data: this.__studyDataClone
      };
      osparc.data.Resources.fetch("studies", "postToTemplate", params)
        .then(taskData => {
          if ("status_href" in taskData) {
            const pollTasks = osparc.data.PollTasks.getInstance();
            const interval = 1000;
            const task = pollTasks.createTask(taskData, interval);
            task.addListener("changeDone", e => {
              if (e.getData()) {
                task.fetchResult()
                  .then(template => {
                    this.fireDataEvent("finished", template);
                    osparc.component.message.FlashMessenger.getInstance().logAs(this.__studyDataClone.name + this.tr(" successfully published as template."), "INFO");
                    btn.setFetching(false);
                  });
              }
            }, this);
          } else {
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while saving as template."), "ERROR");
          }
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while saving as template."), "ERROR");
          btn.setFetching(false);
        });
    }
  }
});
