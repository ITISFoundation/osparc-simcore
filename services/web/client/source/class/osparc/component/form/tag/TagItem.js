/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Represents one tag in the preferences page.
 */
qx.Class.define("osparc.component.form.tag.TagItem", {
  extend: qx.ui.core.Widget,
  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(5));
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
      event: "changeDescription",
      init: ""
    },
    color: {
      check: "Color",
      event: "changeColor",
      init: "background-main-lighter"
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
  members: {
    __tag: null,
    __description: null,
    __nameInput: null,
    __descriptionInput: null,
    __colorInput: null,
    __renderLayout: function() {
      this._removeAll();
      switch (this.getMode()) {
        case this.self().modes.EDIT:
          const nameContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
            width: 90
          });
          nameContainer.add(new qx.ui.basic.Label(this.tr("Name")));
          nameContainer.add(this.getChildControl("nameinput").set({
            value: this.getName()
          }));
          this._add(nameContainer);
          const descInputContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
          descInputContainer.add(new qx.ui.basic.Label(this.tr("Description")));
          descInputContainer.add(this.getChildControl("descriptioninput").set({
            value: this.getDescription()
          }));
          this._add(descInputContainer, {
            flex: 1
          });
          this._add(this.__colorPicker());
          this._add(this.__tagItemEditButtons());
          this.setBackgroundColor("background-main-lighter");
          break;
        default:
          const tagContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox()).set({
            width: 100
          });
          tagContainer.add(this.getChildControl("tag"));
          this._add(tagContainer);
          const descriptionContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          descriptionContainer.add(this.getChildControl("description"));
          this._add(descriptionContainer, {
            flex: 1
          });
          this._add(this.__tagItemButtons());
          this.resetBackgroundColor();
      }
    },
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tag":
          if (this.__tag == null) {
            this.__tag = new osparc.ui.basic.Tag();
            this.bind("name", this.__tag, "value");
            this.bind("color", this.__tag, "color");
          }
          control = this.__tag;
          break;
        case "description":
          if (this.__description == null) {
            this.__description = new qx.ui.basic.Label();
            this.bind("description", this.__description, "value");
          }
          control = this.__description;
          break;
        case "nameinput":
          if (this.__nameInput == null) {
            this.__nameInput = new qx.ui.form.TextField();
          }
          control = this.__nameInput;
          break;
        case "descriptioninput":
          if (this.__descriptionInput == null) {
            this.__descriptionInput = new qx.ui.form.TextField();
          }
          control = this.__descriptionInput;
          break;
        case "colorinput":
          if (this.__colorInput == null) {
            this.__colorInput = new qx.ui.form.TextField().set({
              value: this.getColor(),
              width: 60
            });
            this.__colorInput.bind("value", this.getChildControl("colorbutton"), "backgroundColor");
            this.__colorInput.bind("value", this.getChildControl("colorbutton"), "textColor", {
              converter: value => osparc.utils.Utils.getContrastedTextColor(value)
            });
          }
          control = this.__colorInput;
          break;
        case "colorbutton":
          if (this.__colorButton == null) {
            this.__colorButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/sync-alt/12");
            this.__colorButton.addListener("execute", () => {
              this.getChildControl("colorinput").setValue(osparc.utils.Utils.getRandomColor());
            });
          }
          control = this.__colorButton;
          break;
      }
      return control || this.base(arguments, id);
    },
    __tagItemButtons: function() {
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const editButton = new qx.ui.form.Button(this.tr("Edit")).set({
        appearance: "link-button"
      });
      const deleteButton = new qx.ui.form.Button(this.tr("Delete")).set({
        appearance: "link-button"
      });
      buttonContainer.add(editButton);
      buttonContainer.add(deleteButton);
      editButton.addListener("execute", () => {
        this.setMode(this.self().modes.EDIT);
      });
      deleteButton.addListener("execute", () => {
        console.log("delete", this.getId());
      });
      return buttonContainer;
    },
    __tagItemEditButtons: function() {
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const saveButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/check/12").set({
        appearance: "link-button"
      });
      const cancelButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/times/12").set({
        appearance: "link-button"
      });
      buttonContainer.add(saveButton);
      buttonContainer.add(cancelButton);
      saveButton.addListener("execute", () => {
        console.log("save", this.getId());
      });
      cancelButton.addListener("execute", () => {
        this.setMode(this.self().modes.DISPLAY);
      });
      return buttonContainer;
    },
    __colorPicker: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      container.add(new qx.ui.basic.Label(this.tr("Color")));
      const innerContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const refreshButton = this.getChildControl("colorbutton");
      const colorInput = this.getChildControl("colorinput");
      innerContainer.add(refreshButton);
      innerContainer.add(colorInput);
      container.add(innerContainer);
      return container;
    },
    _applyMode: function() {
      this.__renderLayout();
    }
  }
});
