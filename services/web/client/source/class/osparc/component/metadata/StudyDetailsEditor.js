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
    * @param winWidth {Number} Width for the window, needed for stretching the thumbnail
    */
  construct: function(study, isTemplate, winWidth) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());

    if (study instanceof osparc.data.model.Study) {
      this.__study = study;
      this.__selectedTags = study.getTags();
      this.__workbench = study.getWorkbench();
    } else {
      this.__model = qx.data.marshal.Json.createModel(study);
      this.__selectedTags = study.tags;
      // Workaround: qx serializer is not doing well with uuid as object keys.
      this.__workbench = study.workbench;
    }

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(study, isTemplate, winWidth);
    this.__editView = this.__createEditView(isTemplate);
    this.__stack.add(this.__displayView);
    this.__stack.add(this.__editView);
    this._add(this.__stack);
  },

  events: {
    "updateStudy": "qx.event.type.Event",
    "updateTemplate": "qx.event.type.Event",
    "updateTags": "qx.event.type.Data",
    "closed": "qx.event.type.Event",
    "openStudy": "qx.event.type.Event"
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      apply: "_applyMode"
    }
  },

  statics: {
    popUpInWindow: function(title, studyDetailsEditor, width = 400, height = 400) {
      const win = new qx.ui.window.Window(title).set({
        autoDestroy: true,
        layout: new qx.ui.layout.VBox(),
        appearance: "service-window",
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        contentPadding: 10,
        width: width,
        height: height,
        modal: true
      });
      win.add(studyDetailsEditor);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    __stack: null,
    __fields: null,
    __openButton: null,
    __study: null,
    __model: null,
    __workbench: null,
    __selectedTags: null,

    showOpenButton: function(show) {
      this.__openButton.setVisibility(show ? "visible" : "excluded");
    },

    __createDisplayView: function(study, isTemplate, winWidth) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      displayView.add(this.__createButtons(isTemplate));
      displayView.add(new osparc.component.metadata.StudyDetails(study, winWidth));
      return displayView;
    },

    __createButtons: function(isTemplate) {
      const isCurrentUserOwner = this.__isUserOwner();
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      const canUpdateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.update");

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle"
      })).set({
        marginTop: 10
      });

      const openButton = this.__openButton = new qx.ui.form.Button("Open").set({
        appearance: "md-button"
      });
      osparc.utils.Utils.setIdToWidget(openButton, "openStudyBtn");
      openButton.addListener("execute", () => this.fireEvent("openStudy"), this);
      buttonsLayout.add(openButton);

      const modeButton = new qx.ui.form.Button("Edit", "@FontAwesome5Solid/edit/16").set({
        appearance: "md-button",
        visibility: isCurrentUserOwner && (!isTemplate || canUpdateTemplate) ? "visible" : "excluded"
      });
      osparc.utils.Utils.setIdToWidget(modeButton, "editStudyBtn");
      modeButton.addListener("execute", () => this.setMode("edit"), this);
      buttonsLayout.add(modeButton);

      buttonsLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const permissionsButton = new qx.ui.form.Button(this.tr("Permissions")).set({
        appearance: "md-button"
      });
      osparc.utils.Utils.setIdToWidget(permissionsButton, "permissionsBtn");
      permissionsButton.addListener("execute", e => {
        this.__openPermissions();
      }, this);
      buttonsLayout.add(permissionsButton);

      if (isCurrentUserOwner && (!isTemplate && canCreateTemplate)) {
        const saveAsTemplateButton = new qx.ui.form.Button(this.tr("Save as Template")).set({
          appearance: "md-button"
        });
        osparc.utils.Utils.setIdToWidget(saveAsTemplateButton, "saveAsTemplateBtn");
        saveAsTemplateButton.addListener("execute", e => {
          this.__openSaveAsTemplate();
        }, this);
        buttonsLayout.add(saveAsTemplateButton);
      }

      return buttonsLayout;
    },

    __createEditView: function(isTemplate) {
      const isCurrentUserOwner = this.__isUserOwner();
      const canUpdateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.update");
      const fieldIsEnabled = isCurrentUserOwner && (!isTemplate || canUpdateTemplate);

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

      const saveButton = new qx.ui.form.Button(this.tr("Save"), "@FontAwesome5Solid/save/16").set({
        appearance: "lg-button"
      });
      osparc.utils.Utils.setIdToWidget(saveButton, "studyDetailsEditorSaveBtn");
      saveButton.addListener("execute", e => {
        const btn = e.getTarget();
        btn.setIcon("@FontAwesome5Solid/circle-notch/16");
        btn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        this.__saveStudy(isTemplate, btn);
      }, this);
      const cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "lg-button",
        enabled: isCurrentUserOwner && (!isTemplate || canUpdateTemplate)
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

      buttons.add(saveButton);
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

    __saveStudy: function(isTemplate, btn) {
      const params = {
        url: {
          projectId: this.__model.getUuid()
        },
        data: this.__serializeForm()
      };
      osparc.data.Resources.fetch(isTemplate ? "templates" : "studies", "put", params)
        .then(data => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          this.__model.set(data);
          this.setMode("display");
          this.fireEvent(isTemplate ? "updateTemplate" : "updateStudy");
        })
        .catch(err => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    },

    __openPermissions: function() {
      const permissionsView = new osparc.component.export.Permissions(this.__model);
      const window = permissionsView.createWindow();
      permissionsView.addListener("updateStudy", e => {
        this.fireEvent("updateStudy");
      });
      permissionsView.addListener("finished", e => {
        if (e.getData()) {
          window.close();
        }
      }, this);
      window.open();
    },

    __openSaveAsTemplate: function() {
      const saveAsTemplateView = new osparc.component.export.SaveAsTemplate(this.__model.getUuid(), this.__serializeForm());
      const window = saveAsTemplateView.createWindow();
      saveAsTemplateView.addListener("finished", e => {
        const template = e.getData();
        if (template) {
          this.__model.set(template);
          this.setMode("display");
          this.fireEvent("updateTemplate");
          window.close();
        }
      }, this);
      window.open();
    },

    __serializeForm: function() {
      let data = {};
      if (this.__model === null) {
        data = this.__study.serializeStudy();
      } else {
        data = {
          ...qx.util.Serializer.toNativeObject(this.__model),
          workbench: this.__workbench
        };
      }

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

    __isUserOwner: function() {
      if (this.__model) {
        return this.__model.getPrjOwner() === osparc.auth.Data.getInstance().getEmail();
      }
      return false;
    }
  }
});
