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
 *    const serviceInfo = new osparc.component.metadata.ServiceInfo(selectedService);
 *    this.add(serviceInfo);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.StudyDetailsEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {Object|osparc.data.model.Study} Study (metadata)
    * @param isTemplate {Boolean} Weather the study is template or not
    */
  construct: function(study, isTemplate) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());

    this.__isTemplate = isTemplate;
    this.__selectedTags = study.tags;
    this.__model = qx.data.marshal.Json.createModel(study);

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(study);
    this.__editView = this.__createEditView();
    this.__stack.add(this.__displayView);
    this.__stack.add(this.__editView);
    this._add(this.__stack);

    // Workaround: qx serializer is not doing well with uuid as object keys.
    this.__workbench = study.workbench;
  },

  events: {
    updatedStudy: "qx.event.type.Data",
    updatedTemplate: "qx.event.type.Data",
    updateTags: "qx.event.type.Data",
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
    __selectedTags: null,

    __createDisplayView: function(study) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      displayView.add(this.__createButtons(study));
      displayView.add(new osparc.component.metadata.StudyDetails(study), {
        flex: 1
      });
      return displayView;
    },

    __createButtons: function(study) {
      const isCurrentUserOwner = this.__isCurrentUserOwner();
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      const canUpdateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.update");
      const canExportStudy = osparc.data.Permissions.getInstance().canDo("study.export");

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle"
      })).set({
        marginTop: 10
      });

      const openButton = new qx.ui.form.Button("Open").set({
        appearance: "lg-button"
      });
      osparc.utils.Utils.setIdToWidget(openButton, "openStudyBtn");
      openButton.addListener("execute", () => this.fireEvent("openedStudy"), this);
      buttonsLayout.add(openButton);

      const modeButton = new qx.ui.form.Button("Edit", "@FontAwesome5Solid/edit/16").set({
        appearance: "lg-button",
        visibility: isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate) ? "visible" : "excluded"
      });
      osparc.utils.Utils.setIdToWidget(modeButton, "editStudyBtn");
      modeButton.addListener("execute", () => this.setMode("edit"), this);
      buttonsLayout.add(modeButton);

      buttonsLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const exportButton = new qx.ui.form.Button(this.tr("Export"), "@FontAwesome5Solid/share-alt/16").set({
        appearance: "lg-button",
        visibility: isCurrentUserOwner && !this.__isTemplate && canExportStudy ? "visible" : "excluded"
      });
      osparc.utils.Utils.setIdToWidget(exportButton, "exportStudyBtn");
      exportButton.addListener("execute", e => {
        this.__exportStudy(study);
      }, this);
      buttonsLayout.add(exportButton);

      const saveAsTemplateButton = new qx.ui.form.Button(this.tr("Save as template")).set({
        appearance: "lg-button",
        visibility: isCurrentUserOwner && (!this.__isTemplate || canCreateTemplate) ? "visible" : "excluded"
      });
      osparc.utils.Utils.setIdToWidget(saveAsTemplateButton, "saveAsTemplateBtn");
      saveAsTemplateButton.addListener("execute", e => {
        const btn = e.getTarget();
        btn.setIcon("@FontAwesome5Solid/circle-notch/12");
        btn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        this.__saveAsTemplate(btn);
      }, this);
      buttonsLayout.add(saveAsTemplateButton);

      return buttonsLayout;
    },

    __createEditView: function() {
      const isCurrentUserOwner = this.__isCurrentUserOwner();
      const canUpdateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.update");
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
        appearance: "lg-button"
      });
      osparc.utils.Utils.setIdToWidget(modeButton, "studyDetailsEditorSaveBtn");
      modeButton.addListener("execute", e => {
        const btn = e.getTarget();
        btn.setIcon("@FontAwesome5Solid/circle-notch/16");
        btn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        this.__saveStudy(btn);
      }, this);
      const cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "lg-button",
        enabled: isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate)
      });
      osparc.utils.Utils.setIdToWidget(cancelButton, "studyDetailsEditorCancelBtn");
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
      osparc.utils.Utils.setIdToWidget(name, "studyDetailsEditorTitleFld");
      editView.add(name);
      editView.add(new qx.ui.basic.Label(this.tr("Description")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(description, "studyDetailsEditorDescFld");
      editView.add(description);
      editView.add(new qx.ui.basic.Label(this.tr("Thumbnail")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(thumbnail, "studyDetailsEditorThumbFld");
      editView.add(thumbnail);

      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        editView.add(this.__tagsSection());
      }

      buttons.add(modeButton);
      buttons.add(cancelButton);
      editView.add(buttons);

      return editView;
    },

    __tagsSection: function() {
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      }));
      header.add(new qx.ui.basic.Label(this.tr("Tags")).set({
        font: "text-14"
      }));

      const editButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/edit/14").set({
        appearance: "link-button"
      });
      editButton.addListener("execute", () => {
        const tagManager = new osparc.component.form.tag.TagManager(this.__selectedTags, editButton, "study", this.__model.getUuid());
        tagManager.addListener("changeSelected", evt => {
          this.__selectedTags = evt.getData().selected;
        }, this);
        tagManager.addListener("close", () => {
          this.__renderTags();
          this.fireDataEvent("updateTags", this.__model.getUuid());
        }, this);
      });
      header.add(editButton);

      const tagSection = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      tagSection.add(header);
      tagSection.add(this.__renderTags());
      osparc.store.Store.getInstance().addListener("changeTags", () => this.__renderTags(), this);
      return tagSection;
    },

    __renderTags: function() {
      this.__tagsContainer = this.__tagsContainer || new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this.__tagsContainer.removeAll();
      this.__tagsContainer.setMarginTop(5);
      osparc.store.Store.getInstance().getTags().filter(tag => this.__selectedTags.includes(tag.id))
        .forEach(selectedTag => {
          this.__tagsContainer.add(new osparc.ui.basic.Tag(selectedTag.name, selectedTag.color));
        });
      return this.__tagsContainer;
    },

    __saveStudy: function(btn) {
      const params = {
        url: {
          projectId: this.__model.getUuid()
        },
        data: this.__serializeForm()
      };
      osparc.data.Resources.fetch(this.__isTemplate ? "templates" : "studies", "put", params)
        .then(data => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          this.fireDataEvent(this.__isTemplate ? "updatedTemplate" : "updatedStudy", data);
          this.__model.set(data);
          this.setMode("display");
        })
        .catch(err => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    },

    __exportStudy: function(study) {
      const win = new qx.ui.window.Window(this.tr("Export Study")).set({
        layout: new qx.ui.layout.Grow(),
        contentPadding: 0,
        showMinimize: false,
        showMaximize: false,
        minWidth: 600,
        centerOnAppear: true,
        autoDestroy: true,
        modal: true,
        appearance: "service-window"
      });

      const exportStudy = new osparc.component.widget.ExportStudy(study);
      win.add(exportStudy);
      win.open();
    },

    __saveAsTemplate: function(btn) {
      const params = {
        url: {
          "study_url": this.__model.getUuid()
        },
        data: this.__serializeForm()
      };
      osparc.data.Resources.fetch("templates", "postToTemplate", params)
        .then(template => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          this.fireDataEvent("updatedTemplate", template);
          this.__model.set(template);
          this.setMode("display");
        })
        .catch(err => {
          btn.resetIcon();
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while saving as template."), "ERROR");
        });
    },

    __serializeForm: function() {
      const data = {
        ...qx.util.Serializer.toNativeObject(this.__model),
        workbench: this.__workbench
      };
      for (let key in this.__fields) {
        data[key] = this.__fields[key].getValue();
      }
      // Protect text fields against injecting malicious html/code in them
      [
        "name",
        "description",
        "thumbnail"
      ].forEach(fieldKey => {
        const dirty = data[fieldKey];
        const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
        if (dirty !== clean) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an issue in the text of ") + fieldKey, "ERROR");
        }
        data[fieldKey] = clean;
      }, this);
      data.tags = this.__selectedTags;
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
    },

    __isCurrentUserOwner: function() {
      if (this.__model) {
        return this.__model.getPrjOwner() === osparc.auth.Data.getInstance().getEmail();
      }
      return false;
    }
  }
});
