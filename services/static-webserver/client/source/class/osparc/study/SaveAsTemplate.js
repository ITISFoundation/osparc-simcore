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

qx.Class.define("osparc.study.SaveAsTemplate", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__studyDataClone = osparc.data.model.Study.deepCloneStudyObject(studyData);

    this.__buildLayout();
  },

  events: {
    "publishTemplate": "qx.event.type.Data"
  },

  members: {
    __studyDataClone: null,
    __shareWith: null,
    __publishTemplateBtn: null,
    __copyWData: null,

    __buildLayout: function() {
      const publishWithData = this.__copyWData = new qx.ui.form.CheckBox(this.tr("Publish with data")).set({
        value: true
      });
      this._add(publishWithData);

      const shareWith = this.__shareWith = new osparc.share.ShareTemplateWith(this.__studyDataClone);
      this._add(shareWith);

      const publishTemplateBtn = this.__publishTemplateBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("Publish"),
        allowGrowX: false,
        alignX: "right"
      });
      publishTemplateBtn.addListener("execute", () => this.__publishTemplate(), this);
      this._add(publishTemplateBtn);
    },

    __publishTemplate: function() {
      const readAccessRole = osparc.data.Roles.STUDY["read"];
      // AccessRights will be POSTed after the template is created.
      // No need to add myself, backend will automatically do it
      const accessRights = {};
      this.__studyDataClone["accessRights"] = {};
      const selectedGroupIDs = this.__shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(gid => {
        accessRights[gid] = readAccessRole.accessRights;
      });

      this.fireDataEvent("publishTemplate", {
        "studyData": this.__studyDataClone,
        "copyData": this.__copyWData.getValue(),
        "accessRights": accessRights
      });
    },

    getPublishTemplateButton: function() {
      return this.__publishTemplateBtn;
    }
  }
});
