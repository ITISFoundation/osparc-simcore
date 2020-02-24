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
    this.__formData = formData;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  members: {
    __studyId: null,
    __formData: null,

    __buildLayout: function() {
      const shareWith = new osparc.component.export.ShareWith();
      this._add(shareWith, {
        flex: 1
      });

      const saveAsTemplateBtn = new osparc.ui.form.FetchButton(this.tr("Save as Template")).set({
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

      const params = {
        url: {
          "study_url": this.__studyId
        },
        data: this.__formData
      };
      osparc.data.Resources.fetch("templates", "postToTemplate", params)
        .then(template => {
          this.fireDataEvent("finished", template);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Study successfully saved as template."), "ERROR");
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
