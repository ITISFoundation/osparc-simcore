/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Widget that contains a stack with a StudyDetails and Study Details Editor form.
 *
 * It also provides options for opening the study and creating a template out of it if the
 * user has the permissios.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const serviceInfo = new qxapp.component.metadata.ServiceInfo(selectedService);
 *    this.add(serviceInfo);
 * </pre>
 */

qx.Class.define("qxapp.component.metadata.StudyDetailsEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {Object|qxapp.data.model.Study} Study (metadata)
    * @param isTemplate {Boolean} Weather the study is template or not
    */
  construct: function(study, isTemplate) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());

    this.__model = qx.data.marshal.Json.createModel(study);

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(study);
    this.__editView = this.__createEditView();
    this.__stack.add(this.__displayView);
    this.__stack.add(this.__editView);
    this._add(this.__stack);

    this.__isTemplate = isTemplate;

    // Workaround: qx serializer is not doing well with uuid as object keys.
    this.__workbench = study.workbench;
  },

  events: {
    updatedStudy: "qx.event.type.Data",
    updatedTemplate: "qx.event.type.Data",
    closed: "qx.event.type.Event",
    openedStudy: "qx.event.type.Event"
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      apply: "_applyMode"
    }
  },

  members: {
    __stack: null,
    __workbench: null,
    __model: null,
    __isTemplate: null,
    __fields: null,

    __createDisplayView: function(study) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      displayView.add(this.__createButtons());
      displayView.add(new qxapp.component.metadata.StudyDetails(study), {
        flex: 1
      });
      return displayView;
    },

    __createButtons: function() {
      const canCreateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.create");
      const isCurrentUserOwner = this.__model.getPrjOwner() === qxapp.data.Permissions.getInstance().getLogin();
      const canUpdateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.update");

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle"
      })).set({
        marginTop: 10
      });

      const openButton = new qx.ui.form.Button("Open").set({
        appearance: "md-button"
      });
      openButton.addListener("execute", () => this.fireEvent("openedStudy"), this);
      buttonsLayout.add(openButton);

      const modeButton = new qx.ui.form.Button("Edit", "@FontAwesome5Solid/edit/16").set({
        appearance: "md-button",
        visibility: isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate) ? "visible" : "excluded"
      });
      modeButton.addListener("execute", () => this.setMode("edit"), this);
      buttonsLayout.add(modeButton);

      buttonsLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      if (isCurrentUserOwner && (!this.__isTemplate && canCreateTemplate)) {
        const saveAsTemplateButton = new qx.ui.form.Button(this.tr("Save as template")).set({
          appearance: "md-button"
        });
        saveAsTemplateButton.addListener("execute", e => {
          const btn = e.getTarget();
          btn.setIcon("@FontAwesome5Solid/circle-notch/12");
          btn.getChildControl("icon").getContentElement()
            .addClass("rotate");
          this.__saveAsTemplate(btn);
        }, this);
        buttonsLayout.add(saveAsTemplateButton);
      }

      return buttonsLayout;
    },

    __createEditView: function() {
      const isCurrentUserOwner = this.__model.getPrjOwner() === qxapp.data.Permissions.getInstance().getLogin();
      const canUpdateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.update");
      const fieldIsEnabled = isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate);

      const editView = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignX: "right"
      }));

      this.__fields = {
        name: new qx.ui.form.TextField(this.__model.getName()).set({
          font: "title-18",
          height: 35,
          enabled: fieldIsEnabled
        }),
        description: new qx.ui.form.TextArea(this.__model.getDescription()).set({
          autoSize: true,
          minHeight: 100,
          maxHeight: 500,
          enabled: fieldIsEnabled
        }),
        thumbnail: new qx.ui.form.TextField(this.__model.getThumbnail()).set({
          enabled: fieldIsEnabled
        })
      };

      const modeButton = new qx.ui.form.Button("Save", "@FontAwesome5Solid/save/16").set({
        appearance: "md-button"
      });
      modeButton.addListener("execute", e => {
        const btn = e.getTarget();
        btn.setIcon("@FontAwesome5Solid/circle-notch/16");
        btn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        this.__saveStudy(btn);
      }, this);
      const cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "md-button",
        enabled: isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate)
      });
      cancelButton.addListener("execute", () => this.setMode("display"), this);

      const {
        name,
        description,
        thumbnail
      } = this.__fields;
      editView.add(new qx.ui.basic.Label(this.tr("Title")).set({
        font: "text-14",
        marginTop: 20
      }));
      editView.add(name);
      editView.add(new qx.ui.basic.Label(this.tr("Description")).set({
        font: "text-14"
      }));
      editView.add(description);
      editView.add(new qx.ui.basic.Label(this.tr("Thumbnail")).set({
        font: "text-14"
      }));
      editView.add(thumbnail);
      editView.add(buttons);

      buttons.add(modeButton);
      buttons.add(cancelButton);

      return editView;
    },

    __saveStudy: function(btn) {
      const apiCall = qxapp.io.rest.ResourceFactory.getInstance().createStudyResources().project;
      apiCall.addListenerOnce("putSuccess", e => {
        btn.resetIcon();
        btn.getChildControl("icon").getContentElement()
          .removeClass("rotate");
        this.fireDataEvent(this.__isTemplate ? "updatedTemplate" : "updatedStudy", e);
        const data = e.getData().data;
        this.__model.set(data);
        this.setMode("display");
      }, this);
      apiCall.put({
        "project_id": this.__model.getUuid()
      }, this.__serializeForm());
    },

    __saveAsTemplate: function(btn) {
      const apiCall = qxapp.io.rest.ResourceFactory.getInstance().createStudyResources().projects;
      apiCall.addListenerOnce("postSaveAsTemplateSuccess", e => {
        btn.resetIcon();
        btn.getChildControl("icon").getContentElement()
          .removeClass("rotate");
        this.fireDataEvent("updatedTemplate", e);
        const data = e.getData().data;
        this.__model.set(data);
        this.setMode("display");
      }, this);
      apiCall.addListenerOnce("postSaveAsTemplateError", e => {
        btn.resetIcon();
        console.error(e);
      }, this);
      apiCall.postSaveAsTemplate({
        "study_id": this.__model.getUuid()
      }, this.__serializeForm());
    },

    __serializeForm: function() {
      const data = {
        ...qx.util.Serializer.toNativeObject(this.__model),
        workbench: this.__workbench
      };
      for (let key in this.__fields) {
        data[key] = this.__fields[key].getValue();
      }
      return data;
    },

    _applyMode: function(mode) {
      switch (mode) {
        case "display":
          this.__stack.setSelection([this.__displayView]);
          break;
        case "edit":
          this.__stack.setSelection([this.__editView]);
          break;
      }
    }
  }
});
