/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A Qooxdoo generated form using JSONSchema specification.
 *
 * @asset(object-path/object-path-0-11-4.min.js)
 * @asset(ajv/ajv-6-11-0.min.js)
 * @ignore(Ajv)
 * @ignore(objectPath)
 * @ignore(fetch)
 */
qx.Class.define("osparc.component.form.json.JsonSchemaForm", {
  extend: qx.ui.core.Widget,
  construct: function(schemaUrl, data) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox());
    const ajvLoader = new qx.util.DynamicScriptLoader([
      "/resource/ajv/ajv-6-11-0.min.js",
      "/resource/object-path/object-path-0-11-4.min.js"
    ]);
    ajvLoader.addListener("ready", e => {
      this.__ajv = new Ajv();
      if (schemaUrl) {
        osparc.utils.Utils.fetchJSON(schemaUrl)
          .then(schema => {
            if (this.__validate(schema.$schema, schema)) {
              // If schema is valid
              this.__schema = schema;
              if (data && this.__validate(this.__schema, data)) {
                // Data is valid
                this.__data = data;
              }
              return this.__schema;
            }
            return null;
          })
          .then(this.__render)
          .catch(err => {
            console.error(err);
          });
      }
      if (data) {
        this.setData(data);
      }
      this.fireEvent("ajvReady");
    }, this);
    ajvLoader.addListener("failed", console.error, this);
    this.__render = this.__render.bind(this);
    ajvLoader.start();
  },
  events: {
    "ready": "qx.event.type.Event",
    "ajvReady": "qx.event.type.Event",
    "submit": "qx.event.type.Data"
  },
  members: {
    __inputItems: null,
    __data: null,
    __validationManager: null,
    /**
     * Main function to render a form. It uses the data to prefill the form if it is present.
     *
     * @param {Object} schema JSONSchema used for this form
     */
    __render: function(schema) {
      this._removeAll();
      if (schema) {
        // Render function
        this.__inputItems = [];
        this.__validationManager = new qx.ui.form.validation.Manager();
        this._add(this.__expand(null, schema, this.__data));
        // Buttons
        const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
        this.__submitBtn = new osparc.ui.form.FetchButton(this.tr("Submit"));
        this.__submitBtn.addListener("execute", () => {
          if (this.__isValidData()) {
            const formData = this.toObject(schema);
            if (this.__validate(schema, formData.json)) {
              this.fireDataEvent("submit", formData);
            }
          }
        }, this);
        buttonContainer.add(this.__submitBtn);
        this._add(buttonContainer);
      } else {
        // Validation failed
        this._add(new qx.ui.basic.Label().set({
          value: this.tr("There was an error generating the form or one or more schemas failed to validate. Check your Javascript console for more details."),
          font: "title-16",
          textColor: "service-window-hint",
          rich: true,
          backgroundColor: "material-button-background",
          padding: 10,
          textAlign: "center"
        }));
      }
      this.fireEvent("ready");
    },
    /**
     * Uses Ajv library to validate data against a schema.
     *
     * @param {Object} schema JSONSchema to validate against
     * @param {Object} data Data to be validated
     * @param {Boolean} showMessage Determines whether an error message is displayed to the user
     */
    __validate: function(schema, data, showMessage=true) {
      this.__ajv.validate(schema, data);
      const errors = this.__ajv.errors;
      if (errors) {
        console.error(errors);
        if (showMessage) {
          let message = `${errors[0].dataPath} ${errors[0].message}`;
          osparc.FlashMessenger.logAs(message, "ERROR");
        }
        return false;
      }
      return true;
    },
    /**
     * Function in charge of recursively building the form.
     *
     * @param {String} key Key of the entry in the schema. == null -> root / == -1 -> array item
     * @param {Object} schema Current schema being expanded.
     * @param {Integer} depth Increases as we go deeper into the schema.
     */
    __expand: function(key, schema, data, depth=0, validation) {
      const isArrayItem = key === -1;
      const container = new osparc.component.form.json.JsonSchemaFormItem(key, schema, depth);
      if (schema.type === "object" && schema.properties) {
        // Expanding object's properties
        container.add(this.__expandObject(schema, data, depth, isArrayItem));
      } else if (schema.type === "array") {
        // Arrays allow to create new items with a button
        const arrayContainer = this.__expandArray(schema, data, depth);
        container.add(arrayContainer);
        const addButton = new qx.ui.form.Button(`Add ${objectPath.get(schema, "items.title", schema.title || key)}`, "@FontAwesome5Solid/plus-circle/14");
        addButton.addListener("execute", () => {
          // key = -1 for an array item. we let JsonSchemaFormArray manage the array keys
          arrayContainer.add(this.__expand(-1, schema.items, null, depth+1));
        }, this);
        container.getHeader().add(addButton);
      } else {
        // Leaf
        const input = container.addInput(validation, this.__validationManager);
        if (data) {
          const isNumber = ["number", "integer"].includes(schema.type);
          input.setValue(isNumber ? String(data) : data);
        }
        this.__inputItems.push(container);
      }
      return container;
    },
    /**
     * Function that expands an array if any data was provided.
     *
     * @param {Object} schema Schema for the array.
     * @param {Object} data Array's given data.
     * @param {Integer} depth Current depth into the schema (could be used for styling purposes).
     */
    __expandArray: function(schema, data, depth) {
      const container = new osparc.component.form.json.JsonSchemaFormArray();
      // Add array items
      if (data) {
        data.forEach(item => container.add(this.__expand(-1, schema.items, item, depth+1)));
      }
      return container;
    },
    /**
     * Expands an object property changing its style depending on certain parameters.
     *
     * @param {Object} schema Object's schema to be expanded.
     * @param {Integer} depth Current depth into the schema.
     * @param {Boolean} isArrayItem Used for different styling.
     */
    __expandObject: function(schema, data, depth, isArrayItem) {
      const container = new qx.ui.container.Composite();
      const layoutOptions = {};
      if (isArrayItem) {
        container.setLayout(new qx.ui.layout.Flow(10));
        layoutOptions.flex = 1;
      } else {
        container.setLayout(new qx.ui.layout.VBox());
      }
      Object.entries(schema.properties).forEach(([key, value], index) => {
        // const allProps = Object.values(schema.properties);
        // const nextProp = index < allProps.length - 1 ? allProps[index+1] : null;
        container.add(this.__expand(key, value, data ? data[key] : data, depth+1, {
          required: schema.required && schema.required.includes(key)
        }), {
          // "lineBreak" and "stretch" are not VBox's properties
          // lineBreak: nextProp && nextProp.type === "array" || value.type === "array",
          // stretch: value.type === "array"
        });
      });
      return container;
    },
    /**
     * Uses objectPath library to construct a JS object with the values from the inputs.
     */
    toObject: function(schema) {
      const obj = {
        json: schema.type === "array" ? [] : {}
      };
      const inputMap = {};
      // Retrieve paths
      this.__inputItems.forEach(item => {
        const path = item.getPath();
        if (!path.includes("orphan.osparc.form")) {
          // Don't add orphans (from deleted array items)
          inputMap[path] = item;
        }
      });
      // Clean orphans
      this.__inputItems = this.__inputItems.filter(item => Object.values(inputMap).includes(item));
      // Construct object
      Object.entries(inputMap).forEach(([path, item]) => {
        const input = item.getInput();
        const type = item.getType();
        if (input instanceof osparc.ui.form.FileInput) {
          obj.files = obj.files || [];
          if (input.getFile()) {
            obj.files.push(input.getFile());
          }
        }
        const value = input.getValue();
        if (typeof value !== "undefined" && value !== null) {
          const isNumber = ["number", "integer"].includes(type);
          objectPath.set(obj.json, path, isNumber ? Number(input.getValue()) : input.getValue());
        }
      });
      return obj;
    },
    /**
     * Function that returns an appropriate widget fot the given type.
     *
     * @param {String} type Type of the input that will be used to determine the render behavior
     */
    __getInput: function(type) {
      let input;
      switch (type) {
        default:
          input = new qx.ui.form.TextField();
      }
      return input;
    },
    /**
     * Function for setting the fetching state of the submit button.
     */
    setFetching: function(isFetching) {
      this.__submitBtn.setFetching(isFetching);
    },
    /**
     * Validates fields' data and returns the result.
     */
    __isValidData: function() {
      // Clean garbage from validator (deleted inputs)
      const validatedItems = this.__validationManager.getItems();
      validatedItems.forEach(item => {
        if (!this.getContentElement().getDomElement().contains(item.getContentElement().getDomElement())) {
          this.__validationManager.remove(item);
        }
      });
      return this.__validationManager.validate();
    },
    setSchema: function(schema) {
      if (this.__validate(schema.$schema, schema)) {
        // If schema is valid
        this.__schema = schema;
        if (this.__data && !this.__validate(this.__schema, this.__data)) {
          // Data is invalid
          this.__data = null;
        }
      } else {
        this.__schema = null;
      }
      this.__render(this.__schema);
    },
    setData: function(data) {
      if (data && this.__validate(this.__schema, data)) {
        // Data is valid
        this.__data = data;
        this.__render(this.__schema);
        return;
      }
      if (this.__validate(this.__schema, this.__data)) {
        this.__render(this.__schema);
      }
    }
  }
});
