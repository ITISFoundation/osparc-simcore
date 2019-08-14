/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.widget.StudyDetails", {
  extend: qx.ui.core.Widget,

  construct: function(study, isTemplate) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());
    this.setMarginBottom(20);

    this.__model = qx.data.marshal.Json.createModel(study);

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView();
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
    // __controller: null,
    __stack: null,
    __workbench: null,
    __model: null,
    __isTemplate: null,
    __fields: null,

    __createDisplayView: function() {
      const canCreateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.create");
      const isCurrentUserOwner = this.__model.getPrjOwner() === qxapp.data.Permissions.getInstance().getLogin();
      const canUpdateTemplate = qxapp.data.Permissions.getInstance().canDo("studies.template.update");

      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      const titleAndButtons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle"
      })).set({
        marginTop: 20
      });
      const grid = new qx.ui.layout.Grid(5, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnFlex(0, 1);
      grid.setColumnFlex(1, 1);
      const moreData = new qx.ui.container.Composite(grid);

      const image = new qx.ui.basic.Image().set({
        scale: true,
        allowStretchX: true,
        allowStretchY: true,
        maxHeight: 330,
        alignX: "center"
      });
      const title = new qx.ui.basic.Label().set({
        font: "nav-bar-label",
        allowStretchX: true,
        rich: true
      });
      const description = new qxapp.ui.markdown.Markdown();
      const creationDate = new qx.ui.basic.Label();
      const lastChangeDate = new qx.ui.basic.Label();
      const owner = new qx.ui.basic.Label();

      const modeButton = new qx.ui.form.Button("Edit", "@FontAwesome5Solid/edit/16").set({
        appearance: "md-button",
        visibility: isCurrentUserOwner && (!this.__isTemplate || canUpdateTemplate) ? "visible" : "excluded"
      });
      modeButton.addListener("execute", () => this.setMode("edit"), this);

      const openButton = new qx.ui.form.Button("Open").set({
        appearance: "md-button"
      });
      openButton.addListener("execute", () => this.fireEvent("openedStudy"), this);

      const dateOptions = {
        converter: date => new Date(date).toLocaleString()
      };
      this.__model.bind("name", title, "value");
      this.__model.bind("description", description, "markdown");
      this.__model.bind("thumbnail", image, "source");
      this.__model.bind("thumbnail", image, "visibility", {
        converter: thumbnail => {
          if (thumbnail) {
            return "visible";
          }
          return "excluded";
        }
      });
      this.__model.bind("creationDate", creationDate, "value", dateOptions);
      this.__model.bind("lastChangeDate", lastChangeDate, "value", dateOptions);
      this.__model.bind("prjOwner", owner, "value");

      displayView.add(image);
      titleAndButtons.add(title, {
        flex: 1
      });
      titleAndButtons.add(modeButton);
      titleAndButtons.add(openButton);
      displayView.add(titleAndButtons);
      displayView.add(description);
      moreData.add(new qx.ui.basic.Label(this.tr("Owner")).set({
        font: "title-12"
      }), {
        row: 0,
        column: 0
      });
      moreData.add(new qx.ui.basic.Label(this.tr("Creation date")).set({
        font: "title-12"
      }), {
        row: 1,
        column: 0
      });
      moreData.add(new qx.ui.basic.Label(this.tr("Last change date")).set({
        font: "title-12"
      }), {
        row: 2,
        column: 0
      });
      moreData.add(owner, {
        row: 0,
        column: 1
      });
      moreData.add(creationDate, {
        row: 1,
        column: 1
      });
      moreData.add(lastChangeDate, {
        row: 2,
        column: 1
      });
      displayView.add(moreData);

      if (isCurrentUserOwner && (!this.__isTemplate && canCreateTemplate)) {
        const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
          alignX: "center"
        }));
        const saveAsTemplateButton = new qx.ui.form.Button(this.tr("Save as template"));
        saveAsTemplateButton.addListener("execute", e => {
          const btn = e.getTarget();
          btn.setIcon("@FontAwesome5Solid/circle-notch/12");
          btn.getChildControl("icon").getContentElement()
            .addClass("rotate");
          this.__saveAsTemplate(btn);
        }, this);
        buttons.add(saveAsTemplateButton);
        displayView.add(buttons);
      }

      return displayView;
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
