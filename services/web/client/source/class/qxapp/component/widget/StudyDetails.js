/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.widget.StudyDetails", {
  extend: qx.ui.form.Form,
  include: qx.locale.MTranslation,

  construct: function(study, isTemplate) {
    this.base(arguments);

    this.__createInputs();

    this.__isTemplate = isTemplate;
    this.__controller = new qx.data.controller.Form(qx.data.marshal.Json.createModel(study), this);

    // Workaround: qx serializer is not doing well with uuid as object keys.
    this.__workbench = study.workbench;

    this.__createButtons();
    this.__applyPermissionsOnFields();
  },

  events: {
    updatedStudy: "qx.event.type.Data",
    updatedTemplate: "qx.event.type.Data",
    closed: "qx.event.type.Event",
    openedStudy: "qx.event.type.Event"
  },

  members: {
    __controller: null,
    __workbench: null,
    __isTemplate: null,

    __createInputs: function() {
      this.add(
        new qx.ui.form.TextField(),
        this.tr("Name"),
        null,
        "name"
      );
      this.add(
        new qx.ui.form.TextArea(),
        this.tr("Description"),
        null,
        "description"
      );
      this.add(
        new qx.ui.form.TextField(),
        this.tr("Thumbnail"),
        null,
        "thumbnail"
      );
      this.add(
        new qx.ui.form.TextField().set({
          enabled: false
        }),
        this.tr("Owner"),
        null,
        "prjOwner"
      );
      this.add(
        new qx.ui.form.TextField().set({
          enabled: false
        }),
        this.tr("Creation date"),
        null,
        "creationDate"
      );
      this.add(
        new qx.ui.form.TextField().set({
          enabled: false
        }),
        this.tr("Last change date"),
        null,
        "lastChangeDate"
      );
    },

    __createButtons: function() {
      const apiCall = qxapp.io.rest.ResourceFactory.getInstance().createStudyResources().project;
      const model = this.__controller.getModel();

      // Permissions
      const canCreateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.create");
      const canUpdateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.update");
      const isCurrentUserOwner = model.getPrjOwner() === qxapp.data.Permissions.getInstance().getLogin();

      const openButton = new qx.ui.form.Button(this.tr("Open"));
      openButton.addListener("execute", () => {
        this.fireEvent("openedStudy");
      }, this);
      this.addButton(openButton);

      const saveButton = new qx.ui.form.Button(this.tr("Save"));
      saveButton.addListener("execute", () => {
        apiCall.addListenerOnce("putSuccess", e => {
          this.fireDataEvent(this.__isTemplate ? "updatedTemplate" : "updatedStudy", e);
        }, this);
        apiCall.put({
          "project_id": model.getUuid()
        }, this.serializeForm());
      }, this);
      this.addButton(saveButton);
      saveButton.setEnabled(isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate));

      if (!this.__isTemplate && canCreateTemplate) {
        const saveAsButton = new qx.ui.form.Button(this.tr("Save as template"));
        saveAsButton.addListener("execute", () => {
          apiCall.addListenerOnce("postSaveAsTemplateSuccess", e => {
            this.fireDataEvent("updatedTemplate", e);
          }, this);
          apiCall.addListenerOnce("postSaveAsTemplateError", e => {
            console.error(e);
          }, this);
          apiCall.postSaveAsTemplate({
            "study_id": model.getUuid()
          }, this.serializeForm());
        }, this);
        this.addButton(saveAsButton);
      }

      const cancelButton = new qx.ui.form.Button(this.tr("Cancel"));
      cancelButton.addListener("execute", () => {
        this.fireEvent("closed");
      }, this);
      this.addButton(cancelButton);
    },

    serializeForm: function() {
      const model = this.__controller.getModel();
      return {
        ...qx.util.Serializer.toNativeObject(model),
        workbench: this.__workbench
      };
    },

    __applyPermissionsOnFields: function() {
      const isCurrentUserOwner = this.__controller.getModel().getPrjOwner() === qxapp.data.Permissions.getInstance().getLogin();
      const canUpdateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.update");
      for (let key in this.getItems()) {
        if (["name", "description", "thumbnail"].includes(key)) {
          this.getItems()[key].setEnabled(isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate));
        }
      }
    }
  }
});
