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
 *
 */

qx.Class.define("osparc.component.export.SaveAsTemplate", {
  extend: qx.ui.core.Widget,

  construct: function(studyId, formData) {
    this.base(arguments);

    this.__studyId = studyId;
    this.__formData = osparc.utils.Utils.deepCloneObject(formData);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  statics: {
    createSaveAsTemplateWindow: function(saveAsTemplate) {
      const window = new qx.ui.window.Window("Save as Template").set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 0,
        width: 400,
        height: 300,
        showMinimize: false,
        modal: true
      });
      window.add(saveAsTemplate);
      window.center();
      return window;
    }
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  members: {
    __studyId: null,
    __formData: null,
    __shareWith: null,

    __buildLayout: function() {
      const shareWith = this.__shareWith = new osparc.component.export.ShareWith(this.tr("Make it available to"), "saveAsTemplate");
      this._add(shareWith, {
        flex: 1
      });

      const saveAsTemplateBtn = new osparc.ui.form.FetchButton(this.tr("Publish Template")).set({
        allowGrowX: false,
        alignX: "right"
      });
      saveAsTemplateBtn.addListener("execute", () => {
        this.__saveAsTemplate(saveAsTemplateBtn);
      }, this);
      shareWith.bind("ready", saveAsTemplateBtn, "enabled");
      this._add(saveAsTemplateBtn);
    },

    __saveAsTemplate: function(btn) {
      btn.setFetching(true);

      const selectedGroupIDs = this.__shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(selectedGroupID => {
        this.__formData["accessRights"][selectedGroupID] = "rwx";
      });

      const params = {
        url: {
          "study_id": this.__studyId
        },
        data: this.__formData
      };
      osparc.data.Resources.fetch("templates", "postToTemplate", params)
        .then(template => {
          this.fireDataEvent("finished", template);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Study successfully saved as template."), "INFO");
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while saving as template."), "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    }
  }
});
