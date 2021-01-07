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
 *    const studyDetailsEditor = new osparc.component.metadata.StudyDetailsEditor(studyData, isTemplate, winWidth);
 *    this.add(studyDetailsEditor);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.StudyDetailsEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
    * @param isTemplate {Boolean} Weather the study is template or not
    * @param winWidth {Number} Width for the window, needed for stretching the thumbnail
    */
  construct: function(studyData, isTemplate, winWidth) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());

    this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(studyData, isTemplate, winWidth);
    this.__editView = this.__createEditView(isTemplate);
    this.__stack.add(this.__displayView);
    this.__stack.add(this.__editView);
    this._add(this.__stack);
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateTags": "qx.event.type.Data",
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

  members: {
    __stack: null,
    __fields: null,
    __openButton: null,
    __studyData: null,

    showOpenButton: function(show) {
      this.__openButton.setVisibility(show ? "visible" : "excluded");
    },

    __createDisplayView: function(study, isTemplate, winWidth) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      displayView.add(new osparc.component.metadata.StudyDetails(study, winWidth), {
        flex: 1
      });
      displayView.add(this.__createButtons(isTemplate));
      return displayView;
    },

    __createButtons: function(isTemplate) {
      const isCurrentUserOwner = osparc.data.model.Study.isOwner(this.__studyData);
      const canUpdateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.update");

      const buttonsToolbar = new qx.ui.toolbar.ToolBar();

      const modeButton = new qx.ui.toolbar.Button(this.tr("Edit")).set({
        appearance: "toolbar-md-button",
        visibility: isCurrentUserOwner && (!isTemplate || canUpdateTemplate) ? "visible" : "excluded"
      });
      osparc.utils.Utils.setIdToWidget(modeButton, "editStudyBtn");
      modeButton.addListener("execute", () => this.setMode("edit"), this);
      buttonsToolbar.add(modeButton);

      buttonsToolbar.addSpacer();

      const openButton = this.__openButton = new qx.ui.toolbar.Button(this.tr("Open")).set({
        appearance: "toolbar-md-button"
      });
      osparc.utils.Utils.setIdToWidget(openButton, "openStudyBtn");
      openButton.addListener("execute", () => this.fireEvent("openStudy"), this);
      buttonsToolbar.add(openButton);

      return buttonsToolbar;
    },

    __createEditView: function(isTemplate) {
      const isCurrentUserOwner = osparc.data.model.Study.isOwner(this.__studyData);
      const canUpdateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.update");
      const fieldIsEnabled = isCurrentUserOwner && (!isTemplate || canUpdateTemplate);

      const editView = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));

      this.__fields = {
        name: new qx.ui.form.TextField(this.__studyData.name).set({
          font: "title-16",
          enabled: fieldIsEnabled
        }),
        description: new qx.ui.form.TextArea(this.__studyData.description).set({
          enabled: fieldIsEnabled
        }),
        thumbnail: new qx.ui.form.TextField(this.__studyData.thumbnail).set({
          enabled: fieldIsEnabled
        })
      };

      const {
        name,
        description,
        thumbnail
      } = this.__fields;
      editView.add(new qx.ui.basic.Label(this.tr("Title")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(name, "studyDetailsEditorTitleFld");
      editView.add(name);

      editView.add(new qx.ui.basic.Label(this.tr("Description")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(description, "studyDetailsEditorDescFld");
      editView.add(description, {
        flex: 1
      });

      editView.add(new qx.ui.basic.Label(this.tr("Thumbnail")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(thumbnail, "studyDetailsEditorThumbFld");
      editView.add(thumbnail);

      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        editView.add(this.__tagsSection());
      }

      const saveButton = new qx.ui.toolbar.Button(this.tr("Save"), "@FontAwesome5Solid/save/16").set({
        appearance: "toolbar-md-button"
      });
      osparc.utils.Utils.setIdToWidget(saveButton, "studyDetailsEditorSaveBtn");
      saveButton.addListener("execute", e => {
        const btn = e.getTarget();
        btn.setIcon("@FontAwesome5Solid/circle-notch/16");
        btn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        this.__saveStudy(isTemplate, btn);
      }, this);
      const cancelButton = new qx.ui.toolbar.Button(this.tr("Cancel")).set({
        appearance: "toolbar-md-button",
        enabled: isCurrentUserOwner && (!isTemplate || canUpdateTemplate)
      });
      osparc.utils.Utils.setIdToWidget(cancelButton, "studyDetailsEditorCancelBtn");
      cancelButton.addListener("execute", () => this.setMode("display"), this);

      const buttonsToolbar = new qx.ui.toolbar.ToolBar();
      buttonsToolbar.addSpacer();
      buttonsToolbar.add(saveButton);
      buttonsToolbar.add(cancelButton);
      editView.add(buttonsToolbar);

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
        const tagManager = new osparc.component.form.tag.TagManager(this.__studyData.tags, editButton, "study", this.__studyData.uuid);
        tagManager.addListener("changeSelected", evt => {
          this.__studyData.tags = evt.getData().selected;
        }, this);
        tagManager.addListener("close", () => {
          this.__renderTags();
          this.fireDataEvent("updateTags", this.__studyData.uuid);
        }, this);
      });
      header.add(editButton);

      const tagSection = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      tagSection.add(header);
      tagSection.add(this.__renderTags());
      osparc.store.Store.getInstance().addListener("changeTags", () => {
        if (osparc.auth.Manager.getInstance().isLoggedIn()) {
          this.__renderTags();
        }
      }, this);
      return tagSection;
    },

    __renderTags: function() {
      this.__tagsContainer = this.__tagsContainer || new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this.__tagsContainer.removeAll();
      this.__tagsContainer.setMarginTop(5);
      osparc.store.Store.getInstance().getTags().filter(tag => this.__studyData.tags.includes(tag.id))
        .forEach(selectedTag => {
          this.__tagsContainer.add(new osparc.ui.basic.Tag(selectedTag.name, selectedTag.color));
        });
      return this.__tagsContainer;
    },

    __saveStudy: function(isTemplate, btn) {
      const data = this.__serializeForm();
      const params = {
        url: {
          projectId: this.__studyData.uuid
        },
        data
      };
      osparc.data.Resources.fetch(isTemplate ? "templates" : "studies", "put", params)
        .then(studyData => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          this.setMode("display");
          this.fireDataEvent(isTemplate ? "updateTemplate" : "updateStudy", studyData);
        })
        .catch(err => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    },

    __serializeForm: function() {
      const data = this.__studyData;

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
        if (dirty && dirty !== clean) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was some curation in the text of ") + fieldKey, "WARNING");
        }
        data[fieldKey] = clean;
      }, this);
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
