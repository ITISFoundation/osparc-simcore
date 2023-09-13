/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A Qooxdoo generated item header to be used inside JsonSchemaForm.
 */
qx.Class.define("osparc.form.json.JsonSchemaFormHeader", {
  extend: qx.ui.container.Composite,
  construct: function(schema, depth, isArrayItem) {
    this.base(arguments, new qx.ui.layout.HBox().set({
      alignY: "middle"
    }));
    this.__label = new qx.ui.basic.Label().set({
      allowStretchX: true,
      font: "text-13"
    });
    if (schema.type === "object" || schema.type === "array") {
      let font = "title-14";
      if (depth === 1) {
        font = "title-16";
      } else if (depth === 0) {
        font = "title-18";
      }
      this.__label.setFont(font);
      this.setMarginBottom(10);
    }
    this.add(this.__label, {
      flex: isArrayItem ? 0 : 1
    });
    if (isArrayItem) {
      const deleteButton = new qx.ui.form.Button(this.tr("Remove")).set({
        appearance: "link-button"
      });
      this.add(deleteButton);
      deleteButton.addListener("execute", () => {
        const container = this.getLayoutParent();
        const parent = container.getLayoutParent();
        parent.remove(container);
      }, this);
    }
    this.bind("key", this.__label, "value", {
      converter: key => this.__getHeaderText(key, schema, isArrayItem)
    });
  },
  properties: {
    key: {
      event: "changeKey",
      init: ""
    }
  },
  members: {
    __label: null,
    /**
     * Method that returns an appropriate text for a label.
     */
    __getHeaderText: function(key, schema, isArrayItem) {
      let title = schema.title || key;
      if (isArrayItem) {
        title = schema.title ? `${schema.title} ` : "";
        return title + `#${key + 1}`;
      }
      return title;
    },
    /**
     * Method that returns the label.
     */
    getLabel: function() {
      return this.__label;
    }
  }
});
