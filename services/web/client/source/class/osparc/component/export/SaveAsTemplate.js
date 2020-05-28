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
  extend: osparc.component.export.ShareResourceBase,

  construct: function(studyId, formData) {
    this.base(arguments, studyId);

    this.__formData = osparc.utils.Utils.deepCloneObject(formData);

    this.setHeaderText(this.tr("Make Template accessible to"));
    this.setButtonText(this.tr("Publish"));
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
        showMaximize: false,
        showMinimize: false,
        modal: true
      });
      window.add(saveAsTemplate);
      window.center();
      return window;
    }
  },

  members: {
    __formData: null,

    // overridden
    _shareResource: function(btn) {
      btn.setFetching(true);

      const selectedGroupIDs = this._shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(selectedGroupID => {
        this.__formData["accessRights"][selectedGroupID] = "rwx";
      });

      const params = {
        url: {
          "study_id": this._studyId
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
