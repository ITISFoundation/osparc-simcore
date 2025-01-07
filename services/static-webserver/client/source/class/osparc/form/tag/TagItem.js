/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Represents one tag in the preferences page.
 */
qx.Class.define("osparc.form.tag.TagItem", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(5));
    this.__validationManager = new qx.ui.form.validation.Manager();
  },

  statics: {
    modes: {
      DISPLAY: "display",
      EDIT: "edit"
    }
  },

  properties: {
    tag: {
      check: "osparc.data.model.Tag",
      nullable: false,
      init: null,
      event: "changeTag",
      apply: "__applyTag",
    },

    id: {
      check: "Integer"
    },

    name: {
      check: "String",
      event: "changeName",
      init: ""
    },

    description: {
      check: "String",
      nullable: true,
      event: "changeDescription",
      init: ""
    },

    color: {
      check: "Color",
      event: "changeColor",
      init: "#303030"
    },

    myAccessRights: {
      check: "Object",
      nullable: false,
      event: "changeMyAccessRights",
    },

    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAccessRights",
    },

    mode: {
      check: "String",
      init: "display",
      nullable: false,
      apply: "__applyMode"
    },

    appearance: {
      init: "tagitem",
      refine: true
    }
  },

  events: {
    "tagSaved": "qx.event.type.Event",
    "cancelNewTag": "qx.event.type.Event",
    "deleteTag": "qx.event.type.Event"
  },

  members: {
    __validationManager: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tag":
          control = new osparc.ui.basic.Tag();
          this.bind("name", control, "value");
          this.bind("color", control, "color");
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            rich: true,
            allowGrowX: true,
          });
          this.bind("description", control, "value");
          break;
        case "shared-icon":
          control = new qx.ui.basic.Image().set({
            minWidth: 30,
            alignY: "middle",
            cursor: "pointer",
          });
          osparc.dashboard.CardBase.populateShareIcon(control, this.getAccessRights())
          control.addListener("tap", () => this.__openAccessRights(), this);
          break;
        case "name-input":
          control = new qx.ui.form.TextField().set({
            required: true
          });
          this.__validationManager.add(control);
          control.getContentElement().setAttribute("autocomplete", "off");
          break;
        case "description-input":
          control = new qx.ui.form.TextArea().set({
            autoSize: true,
            minimalLineHeight: 1
          });
          break;
        case "color-input":
          control = new qx.ui.form.TextField().set({
            value: this.getColor(),
            width: 60,
            required: true
          });
          control.bind("value", this.getChildControl("color-button"), "backgroundColor");
          control.bind("value", this.getChildControl("color-button"), "textColor", {
            converter: value => osparc.utils.Utils.getContrastedBinaryColor(value)
          });
          this.__validationManager.add(control, osparc.utils.Validators.hexColor);
          break;
        case "color-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/sync-alt/12");
          control.addListener("execute", () => {
            this.getChildControl("color-input").setValue(osparc.utils.Utils.getRandomColor());
          }, this);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyTag: function(tag) {
      tag.bind("tagId", this, "id");
      tag.bind("name", this, "name");
      tag.bind("description", this, "description");
      tag.bind("color", this, "color");
      tag.bind("myAccessRights", this, "myAccessRights");
      tag.bind("accessRights", this, "accessRights");

      this.__renderLayout();
    },

    /**
     * Renders this tag item from scratch.
     */
    __renderLayout: function() {
      this._removeAll();
      if (this.getMode() === this.self().modes.EDIT) {
        this.__renderEditMode();
      } else if (this.getMode() === this.self().modes.DISPLAY) {
        this.__renderDisplayMode();
      }
    },

    __renderEditMode: function() {
      const nameContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        width: 90
      });
      nameContainer.add(new qx.ui.basic.Label(this.tr("Name")).set({
        buddy: this.getChildControl("name-input")
      }));
      nameContainer.add(this.getChildControl("name-input").set({
        value: this.getName()
      }));
      this._add(nameContainer);
      const descInputContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      descInputContainer.add(new qx.ui.basic.Label(this.tr("Description")).set({
        buddy: this.getChildControl("description-input")
      }));
      descInputContainer.add(this.getChildControl("description-input").set({
        value: this.getDescription()
      }));
      this._add(descInputContainer, {
        flex: 1
      });
      this._add(this.__colorPicker());
      this._add(this.__tagItemEditButtons());
    },

    __renderDisplayMode: function() {
      this._add(this.getChildControl("tag"));
      this._add(this.getChildControl("description"), {
        flex: 1
      });
      this._add(this.getChildControl("shared-icon"));
      this._add(this.__tagItemButtons());
      this.resetBackgroundColor();
    },

    __openAccessRights: function() {
      const permissionsView = new osparc.share.CollaboratorsTag(this.getTag());
      const title = this.tr("Share Tag");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 600, 600);

      permissionsView.addListener("updateAccessRights", () => {
        const accessRights = this.getTag().getAccessRights();
        if (accessRights) {
          const sharedIcon = this.getChildControl("shared-icon");
          osparc.dashboard.CardBase.populateShareIcon(sharedIcon, accessRights);
        }
      }, this);
    },

    /**
     * Generates and returns the buttons for deleting and editing an existing label (display mode)
     */
    __tagItemButtons: function() {
      const canIWrite = osparc.share.CollaboratorsTag.canIWrite(this.getMyAccessRights());
      const canIDelete = osparc.share.CollaboratorsTag.canIDelete(this.getMyAccessRights());

      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const editButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/pencil-alt/12",
        toolTipText: this.tr("Edit"),
        enabled: canIWrite,
      });
      const deleteButton = new osparc.ui.form.FetchButton().set({
        appearance: "danger-button",
        icon: "@FontAwesome5Solid/trash/12",
        toolTipText: this.tr("Delete"),
        enabled: canIDelete,
      });
      buttonContainer.add(editButton);
      buttonContainer.add(deleteButton);
      editButton.addListener("execute", () => this.setMode(this.self().modes.EDIT), this);
      deleteButton.addListener("execute", () => {
        deleteButton.setFetching(true);
        osparc.store.Tags.getInstance().deleteTag(this.getId())
          .then(() => this.fireEvent("deleteTag"))
          .catch(console.error)
          .finally(() => deleteButton.setFetching(false));
      }, this);
      return buttonContainer;
    },
    /**
     * Generates and returns the buttons for cancelling edition and saving tag of a new or existing label (edit mode)
     */
    __tagItemEditButtons: function() {
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const saveButton = new osparc.ui.form.FetchButton(null, "@FontAwesome5Solid/check/12").set({
        appearance: "link-button",
        paddingTop: 15, // avoid buddy text
        alignY: "middle"
      });
      const cancelButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/times/12").set({
        appearance: "link-button",
        paddingTop: 15, // avoid buddy text
        alignY: "middle"
      });
      buttonContainer.add(saveButton);
      buttonContainer.add(cancelButton);
      saveButton.addListener("execute", () => {
        if (this.__validationManager.validate()) {
          const data = this.__serializeData();
          saveButton.setFetching(true);
          const tagsStore = osparc.store.Tags.getInstance();
          if (this.isPropertyInitialized("id")) {
            tagsStore.putTag(this.getId(), data)
              .then(tag => this.setTag(tag))
              .catch(console.error)
              .finally(() => {
                this.fireEvent("tagSaved");
                this.setMode(this.self().modes.DISPLAY);
                saveButton.setFetching(false);
              });
          } else {
            let newTag = null;
            tagsStore.postTag(data)
              .then(tag => {
                newTag = tag;
                return tagsStore.fetchAccessRights(tag);
              })
              .then(() => this.setTag(newTag))
              .catch(console.error)
              .finally(() => {
                this.fireEvent("tagSaved");
                this.setMode(this.self().modes.DISPLAY);
                saveButton.setFetching(false);
              });
          }
        }
      }, this);
      cancelButton.addListener("execute", () => {
        if (this.isPropertyInitialized("id")) {
          this.__validationManager.reset();
          this.setMode(this.self().modes.DISPLAY);
        } else {
          this.fireEvent("cancelNewTag");
        }
      }, this);
      return buttonContainer;
    },
    /**
     * Generates and returns the color input (edit mode)
     */
    __colorPicker: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      container.add(new qx.ui.basic.Label(this.tr("Color")).set({
        buddy: this.getChildControl("color-input")
      }));
      const innerContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const refreshButton = this.getChildControl("color-button");
      const colorInput = this.getChildControl("color-input");
      innerContainer.add(refreshButton);
      innerContainer.add(colorInput);
      container.add(innerContainer);
      return container;
    },
    /**
     * Creates an object containing the updated tag info
     */
    __serializeData: function() {
      const name = this.getChildControl("name-input").getValue();
      const description = this.getChildControl("description-input").getValue();
      const color = this.getChildControl("color-input").getValue();
      return {
        name: name.trim(),
        description: description ? description.trim() : "",
        color: color
      };
    },
    __applyMode: function() {
      this.__renderLayout();
    }
  }
});
