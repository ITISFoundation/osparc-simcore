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
      osparc.utils.Utils.fetchJSON(schemaUrl)
        .then(schema => {
          if (this.__validate(schema.$schema, schema)) {
            // If schema is valid
            if (data && this.__validate(schema, data)) {
              // Validate data if present
              this.__data = data;
            }
            return schema;
          }
          return null;
        })
        .then(this.__render)
        .catch(err => {
          console.error(err);
          this.__render(null);
        });
    }, this);
    ajvLoader.addListener("failed", console.error, this);
    this.__render = this.__render.bind(this);
    ajvLoader.start();
  },
  events: {
    "ready": "qx.event.type.Event"
  },
  members: {
    __inputItems: null,
    __data: null,
    __render: function(schema) {
      this._removeAll();
      if (schema) {
        // Render function
        this.__inputItems = new qx.type.Array();
        this._add(this.__expand(null, schema, this.__data));
        // Buttons
        const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
        const submitBtn = new qx.ui.form.Button(this.tr("Submit"));
        submitBtn.addListener("execute", () => console.log(this.toObject()), this);
        buttonContainer.add(submitBtn);
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
    __validate: function(schema, data) {
      const ajv = new Ajv();
      ajv.validate(schema, data)
      if (ajv.errors) {
        console.error(ajv.errors);
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
    __expand: function(key, schema, data, depth=0) {
      const isArrayItem = key === -1;
      const container = new osparc.component.form.json.JsonSchemaFormItem(key, schema, depth);
      if (schema.type === "object" && schema.properties) {
        // Expanding object's properties
        container.add(this.__expandObject(schema.properties, depth, data, isArrayItem));
      } else if (schema.type === "array") {
        // Arrays allow to create new items with a button
        const arrayContainer = new osparc.component.form.json.JsonSchemaFormArray();
        container.add(arrayContainer);
        const addButton = new qx.ui.form.Button(`Add ${objectPath.get(schema, "items.title", key)}`, "@FontAwesome5Solid/plus-circle/14");
        addButton.addListener("execute", () => {
          // key = -1 for an array item. we let JsonSchemaFormArray manage the array keys
          arrayContainer.add(this.__expand(-1, schema.items, data, depth+1));
        }, this);
        // Add array items
        data.forEach(item => arrayContainer.add(this.__expand(-1, schema.items, item, depth+1)));
        container.getHeader().add(addButton);
      } else {
        // Leaf
        const input = container.addInput();
        if (data) {
          input.setValue(data);
        }
        this.__inputItems.push(container);
      }
      return container;
    },
    /**
     * Expands an object property changing its style depending on certain parameters.
     * 
     * @param {Object} properties Object's properties to be expanded.
     * @param {Integer} depth Current depth into the schema.
     * @param {Boolean} isArrayItem Used for different styling.
     */
    __expandObject: function(properties, depth, data, isArrayItem) {
      const container = new qx.ui.container.Composite();
      const layoutOptions = {};
      if (isArrayItem) {
        container.setLayout(new qx.ui.layout.Flow(10));
        layoutOptions.flex = 1;
      } else {
        container.setLayout(new qx.ui.layout.VBox());
      }
      Object.entries(properties).forEach(([key, value]) => container.add(this.__expand(key, value, data[key], depth+1)));
      return container;
    },
    /**
     * Uses objectPath library to construct a JS object with the values of the inputs.
     */
    toObject: function() {
      const obj = {};
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
      Object.entries(inputMap).forEach(([path, item]) => objectPath.set(obj, path, item.getInput().getValue()));
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
    }
  }
});
