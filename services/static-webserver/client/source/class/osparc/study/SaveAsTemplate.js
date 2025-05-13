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
    __form: null,
    __publishTemplateBtn: null,

    __buildLayout: function() {
      const form = this.__form = new qx.ui.form.Form();
      this._add(new qx.ui.form.renderer.Single(form));

      const publishWithData = new qx.ui.form.CheckBox().set({
        value: true,
        iconPosition: "right",
      });
      form.add(publishWithData, this.tr("Publish with data"), null, "publishWithData");

      if (osparc.product.Utils.isS4LProduct()) {
        const templateTypeSB = new qx.ui.form.SelectBox().set({
          allowGrowX: false,
        });
        const templateTypes = [{
          label: "Tutorial",
          id: null,
        }, {
          label: "Hypertool",
          id: osparc.data.model.StudyUI.HYPERTOOL_TYPE,
        }]
        templateTypes.forEach(tempType => {
          const tItem = new qx.ui.form.ListItem(tempType.label, null, tempType.id);
          templateTypeSB.add(tItem);
        });
        form.add(templateTypeSB, this.tr("Template Type"), null, "templateType");
      }

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
      const publishWithDataCB = this.__form.getItem("publishWithData");
      const templateTypeSB = this.__form.getItem("templateType");
      const templateType = templateTypeSB ? templateTypeSB.getSelection()[0].getModel() : null;

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
        "copyData": publishWithDataCB.getValue(),
        "accessRights": accessRights,
        "templateType": templateType,
      });
    },

    getPublishTemplateButton: function() {
      return this.__publishTemplateBtn;
    }
  }
});
