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
  construct: function(studyData, makeItPublic = false) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__studyDataClone = osparc.data.model.Study.deepCloneStudyObject(studyData);
    this.__makeItPublic = makeItPublic;

    this.__buildLayout();
  },

  events: {
    "publishTemplate": "qx.event.type.Data"
  },

  members: {
    __studyDataClone: null,
    __makeItPublic: null,
    __form: null,
    __createTemplateBtn: null,

    __buildLayout: function() {
      let introText = "";
      if (this.__makeItPublic) {
        introText += this.tr("This project will be published and accessible to everyone.");
        introText += "<br>";
        introText += this.tr("All users will see it and can copy it.");
      } else {
        introText += this.tr("This project will be saved as a template.");
        introText += "<br>";
        introText += this.tr("The users you select will be able to see it and copy it.");
      }
      this._add(new qx.ui.basic.Label(introText).set({
        font: "text-14",
        rich: true,
      }));

      const form = this.__form = new qx.ui.form.Form();
      this._add(new qx.ui.form.renderer.Single(form));

      const publishWithData = new qx.ui.form.CheckBox().set({
        value: true,
        iconPosition: "right",
      });
      form.add(publishWithData, this.tr("Publish with data"), null, "publishWithData");

      if (osparc.data.Permissions.getInstance().isTester()) {
        const templateTypeSB = osparc.study.Utils.createTemplateTypeSB();
        form.add(templateTypeSB, this.tr("Template Type"), null, "templateType");
      }

      if (!this.__makeItPublic) {
        const shareWith = this.__shareWith = new osparc.share.ShareTemplateWith(this.__studyDataClone);
        shareWith.exclude(); // for now, hide the shareWith widget
        this._add(shareWith);
      }

      const createTemplateBtn = this.__createTemplateBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.__makeItPublic ? this.tr("Publish") : this.tr("Create Template"),
        allowGrowX: false,
        alignX: "right"
      });
      createTemplateBtn.addListener("execute", () => this.__createTemplate(), this);
      this._add(createTemplateBtn);
    },

    __createTemplate: function() {
      const publishWithDataCB = this.__form.getItem("publishWithData");
      const templateTypeSB = this.__form.getItem("templateType");
      const templateType = templateTypeSB ? templateTypeSB.getSelection()[0].getModel() : null;

      // AccessRights will be POSTed after the template is created.
      // No need to add myself, backend will automatically do it
      const accessRights = {};
      this.__studyDataClone["accessRights"] = {};
      if (this.__makeItPublic) {
        // share the template with the everyone group
        const groupsStore = osparc.store.Groups.getInstance();
        const groupProductEveryone = groupsStore.getEveryoneProductGroup();
        accessRights[groupProductEveryone.getGroupId()] = osparc.data.Roles.STUDY["read"].accessRights;
      } else {
        const selectedGroupIDs = this.__shareWith.getSelectedGroups();
        const readAccessRole = osparc.data.Roles.STUDY["read"];
        selectedGroupIDs.forEach(gid => {
          accessRights[gid] = readAccessRole.accessRights;
        });
      }

      this.fireDataEvent("publishTemplate", {
        "studyData": this.__studyDataClone,
        "copyData": publishWithDataCB.getValue(),
        "accessRights": accessRights,
        "templateType": templateType,
      });
    },

    getCreateTemplateButton: function() {
      return this.__createTemplateBtn;
    }
  }
});
