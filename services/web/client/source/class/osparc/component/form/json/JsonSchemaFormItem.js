/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A generic form item to be used inside JsonSchemaForm.
 * It generates an appropriate header than can dynamically change for array items (if the user deletes one element).
 * Manages this dynamic keys to update the header and generate consistent output data object.
 */
qx.Class.define("osparc.component.form.json.JsonSchemaFormItem", {
  extend: qx.ui.container.Composite,
  construct: function(key, schema, depth) {
    this.base(arguments, new qx.ui.layout.VBox());
    this.setMarginBottom(10);
    if (key !== null) {
      this.setKey(key);
    }
    this.__isArrayItem = key === -1;
    this.__schema = schema;
    this.__header = new osparc.component.form.json.JsonSchemaFormHeader(schema, depth, this.__isArrayItem);
    this.add(this.__header);
    this.bind("key", this.__header, "key");
  },
  properties: {
    key: {
      event: "changeKey",
      init: ""
    }
  },
  members: {
    __header: null,
    __isArrayItem: null,
    __header: null,
    __input: null,
    /**
     * Makes this item a final input (leaf).
     */
    addInput: function() {
      const input = this.__input = this.__getInputElement();
      this.__header.getLabel().setBuddy(input);
      this.add(input);
      if (this.__schema.description) {
        this.add(new qx.ui.basic.Label(this.__schema.description).set({
          font: "text-12-italic",
          marginTop: 3
        }));
      }
      return input;
    },
    /**
     * Gets the generated header
     */
    getHeader: function() {
      return this.__header;
    },
    /**
     * Gets the generated header
     */
    getInput: function() {
      return this.__input;
    },
    /**
     * Function that returns an appropriate widget fot the given type.
     * 
     * @param {String} type Type of the input that will be used to determine the render behavior
     */
    __getInputElement: function() {
      let input;
      switch (this.__schema.type) {
        default:
          input = new qx.ui.form.TextField();
      }
      return input;
    },
    /**
     * Function that recursively constructs the path of this form item.
     */
    getPath: function() {
      const isForm = layoutItem => layoutItem instanceof osparc.component.form.json.JsonSchemaForm;
      const isFormItem = layoutItem  => layoutItem instanceof osparc.component.form.json.JsonSchemaFormItem;
      let parent = this.getLayoutParent();
      // Search for its parent FormItem
      while (!isFormItem(parent) && !isForm(parent) && parent) {
        parent = parent.getLayoutParent();
      }
      if (isFormItem(parent)) {
        const parentPath = parent.getPath();
        return parentPath ? `${parentPath}.${this.getKey()}` : `${this.getKey()}`;
      }
      if (isForm(parent)) {
        return null;
      }
      return "orphan.osparc.form";
    }
  }
});
