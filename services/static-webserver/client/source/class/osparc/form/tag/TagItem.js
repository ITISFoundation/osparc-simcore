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
    this.__renderLayout();
  },

  statics: {
    modes: {
      DISPLAY: "display",
      EDIT: "edit"
    }
  },

  properties: {
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
    accessRights: {
      check: "Object",
      nullable: false,
      apply: "__renderLayout",
      event: "changeAccessRights"
    },
    mode: {
      check: "String",
      init: "display",
      nullable: false,
      apply: "_applyMode"
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
    __tag: null,
    __description: null,
    __nameInput: null,
    __descriptionInput: null,
    __colorInput: null,
    __colorButton: null,
    __loadingIcon: null,
    __validationManager: null,
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
        buddy: this.getChildControl("nameinput")
      }));
      nameContainer.add(this.getChildControl("nameinput").set({
        value: this.getName()
      }));
      this._add(nameContainer);
      const descInputContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      descInputContainer.add(new qx.ui.basic.Label(this.tr("Description")).set({
        buddy: this.getChildControl("descriptioninput")
      }));
      descInputContainer.add(this.getChildControl("descriptioninput").set({
        value: this.getDescription()
      }));
      this._add(descInputContainer, {
        flex: 1
      });
      this._add(this.__colorPicker());
      this._add(this.__tagItemEditButtons());
    },
    __renderDisplayMode: function() {
      const tagContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox()).set({
        width: 100
      });
      tagContainer.add(this.getChildControl("tag"));
      this._add(tagContainer);
      const descriptionContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      descriptionContainer.add(this.getChildControl("description"), {
        width: "100%"
      });
      this._add(descriptionContainer, {
        flex: 1
      });
      this._add(this.__tagItemButtons());
      this.resetBackgroundColor();
    },
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tag":
          // Tag sample on display mode
          if (this.__tag === null) {
            this.__tag = new osparc.ui.basic.Tag();
            this.bind("name", this.__tag, "value");
            this.bind("color", this.__tag, "color");
          }
          control = this.__tag;
          break;
        case "description":
          // Description label on display mode
          if (this.__description === null) {
            this.__description = new qx.ui.basic.Label().set({
              rich: true
            });
            this.bind("description", this.__description, "value");
          }
          control = this.__description;
          break;
        case "nameinput":
          // Tag name input in edit mode
          if (this.__nameInput === null) {
            this.__nameInput = new qx.ui.form.TextField().set({
              required: true
            });
            this.__validationManager.add(this.__nameInput);
            this.__nameInput.getContentElement().setAttribute("autocomplete", "off");
          }
          control = this.__nameInput;
          break;
        case "descriptioninput":
          // Tag description input in edit mode
          if (this.__descriptionInput === null) {
            this.__descriptionInput = new qx.ui.form.TextArea().set({
              autoSize: true,
              minimalLineHeight: 1
            });
          }
          control = this.__descriptionInput;
          break;
        case "colorinput":
          // Color input in edit mode
          if (this.__colorInput === null) {
            this.__colorInput = new qx.ui.form.TextField().set({
              value: this.getColor(),
              width: 60,
              required: true
            });
            this.__colorInput.bind("value", this.getChildControl("colorbutton"), "backgroundColor");
            this.__colorInput.bind("value", this.getChildControl("colorbutton"), "textColor", {
              converter: value => osparc.utils.Utils.getContrastedBinaryColor(value)
            });
            this.__validationManager.add(this.__colorInput, osparc.utils.Validators.hexColor);
          }
          control = this.__colorInput;
          break;
        case "colorbutton":
          // Random color generator button in edit mode
          if (this.__colorButton === null) {
            this.__colorButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/sync-alt/12");
            this.__colorButton.addListener("execute", () => {
              this.getChildControl("colorinput").setValue(osparc.utils.Utils.getRandomColor());
            }, this);
          }
          control = this.__colorButton;
          break;
      }
      return control || this.base(arguments, id);
    },
    /**
     * Generates and returns the buttons for deleting and editing an existing label (display mode)
     */
    __tagItemButtons: function() {
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const editButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/pencil-alt/12",
        toolTipText: this.tr("Edit")
      });
      const deleteButton = new osparc.ui.form.FetchButton().set({
        appearance: "danger-button",
        icon: "@FontAwesome5Solid/trash/12",
        toolTipText: this.tr("Delete")
      });
      if (this.isPropertyInitialized("accessRights")) {
        editButton.setEnabled(this.getAccessRights()["write"]);
        deleteButton.setEnabled(this.getAccessRights()["delete"]);
      }
      buttonContainer.add(editButton);
      buttonContainer.add(deleteButton);
      editButton.addListener("execute", () => this.setMode(this.self().modes.EDIT), this);
      deleteButton.addListener("execute", () => {
        deleteButton.setFetching(true);
        const params = {
          url: {
            tagId: this.getId()
          }
        };
        osparc.data.Resources.fetch("tags", "delete", params, this.getId())
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
          const params = {
            data
          };
          saveButton.setFetching(true);
          let fetch;
          if (this.isPropertyInitialized("id")) {
            params.url = {
              tagId: this.getId()
            };
            fetch = osparc.data.Resources.fetch("tags", "put", params);
          } else {
            fetch = osparc.data.Resources.fetch("tags", "post", params);
          }
          fetch
            .then(tag => this.set(tag))
            .catch(console.error)
            .finally(() => {
              this.fireEvent("tagSaved");
              this.setMode(this.self().modes.DISPLAY);
              saveButton.setFetching(false);
            });
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
        buddy: this.getChildControl("colorinput")
      }));
      const innerContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const refreshButton = this.getChildControl("colorbutton");
      const colorInput = this.getChildControl("colorinput");
      innerContainer.add(refreshButton);
      innerContainer.add(colorInput);
      container.add(innerContainer);
      return container;
    },
    /**
     * Creates an object containing the udpated tag info
     */
    __serializeData: function() {
      return {
        name: this.getChildControl("nameinput").getValue().trim(),
        description: this.getChildControl("descriptioninput").getValue().trim(),
        color: this.getChildControl("colorinput").getValue()
      };
    },
    _applyMode: function() {
      this.__renderLayout();
    }
  }
});
