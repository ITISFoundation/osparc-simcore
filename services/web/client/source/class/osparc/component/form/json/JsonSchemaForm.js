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
 * @ignore(Ajv)
 * @ignore(objectPath)
 * @ignore(fetch)
 */
qx.Class.define("osparc.component.form.json.JsonSchemaForm", {
  extend: qx.ui.core.Widget,
  construct: function(schemaUrl) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox());
    const ajvLoader = new qx.util.DynamicScriptLoader([
      "https://cdnjs.cloudflare.com/ajax/libs/ajv/6.11.0/ajv.min.js",
      "/resource/object-path/object-path-0-11-4.min.js"
    ]);
    ajvLoader.addListener("ready", e => {
      osparc.utils.Utils.fetchJSON(schemaUrl)
        .then(this.__validateSchema)
        .then(this.__render)
        .catch(err => {
          console.error(err);
          this.__render(null);
        });
    }, this);
    this.__render = this.__render.bind(this);
    this.__validateSchema = this.__validateSchema.bind(this);
    ajvLoader.start();
  },
  events: {
    "ready": "qx.event.type.Event"
  },
  members: {
    __schema: null,
    __inputsMap: null,
    __render: function(schema) {
      this._removeAll();
      this.__inputsMap = {};
      if (schema) {
        this.__schema = schema;
        // Render function
        this._add(this.__expand(null, schema));
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
    __validateSchema: function(schema) {
      return new Promise((resolve, reject) => {
        const ajv = new Ajv();
        ajv.validate(schema.$schema, schema)
        if (ajv.errors) {
          reject(ajv.errors);
        }
        resolve(schema);
      });
    },
    /**
     * Function in charge of recursively building the form.
     * 
     * @param {String} key Key of the entry in the schema.
     * @param {Object} schema Current schema being expanded.
     * @param {Integer} depth Increases as we go deeper into the schema.
     * @param {String} path Constructs the input path.
     */
    __expand: function(key, schema, depth=0, path="") {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        marginBottom: 10
      });
      const isArrayItem = Number.isInteger(key);
      if (schema.type === "object" || schema.type === "array") {
        // Objects and arrays have a section with a header and some hierarchical distinction
        const header = this.__getHeader(key, schema, depth, isArrayItem);
        container.add(header);
        
        if (schema.type === "object" && schema.properties) {
          // Expanding object's properties
          const content = this.__expandObject(schema.properties, depth, path, isArrayItem);
          container.add(content);
          // Object.entries(schema.properties).forEach(([key, value]) => container.add(this.__expand(key, value, depth+1, `${path}.${key}`)));
        } else if (schema.type === "array") {
          // Arrays allow to create new items with a button
          let pos = 0;
          const arrayContainer = new osparc.component.form.json.JsonSchemaFormArray();
          container.add(arrayContainer);
          const addButton = new qx.ui.form.Button(`Add ${objectPath.get(schema, "items.title", key)}`, "@FontAwesome5Solid/plus-circle/14");
          addButton.addListener("execute", () => {
            arrayContainer.add(this.__expand(pos, schema.items, depth+1, `${path}.${pos++}`));
          }, this);
          header.add(addButton);
        }
      } else {
        // Leaf (render input depending on type)
        const input = this.__getInput(schema.type);
        // Input label
        container.add(new qx.ui.basic.Label(schema.title || key).set({
          buddy: input
        }));
        const fixedPath = path.substring(1); // Removes starting dot from path
        this.__inputsMap[fixedPath] = input; // Keeps a map of the inputs with their paths to retrieve their values later
        container.add(input);
        if (schema.description) {
          container.add(new qx.ui.basic.Label(schema.description).set({
            font: "text-12-italic",
            marginTop: 3
          }));
        }
      }
      return container;
    },
    /**
     * Expands an object property changing its style depending on certain parameters.
     * 
     * @param {Object} properties Object's properties to be expanded.
     * @param {Integer} depth Current depth into the schema.
     * @param {String} path Current result object path.
     * @param {Boolean} isArrayItem Used for different styling.
     */
    __expandObject: function(properties, depth, path, isArrayItem) {
      const container = new qx.ui.container.Composite();
      const layoutOptions = {};
      if (isArrayItem) {
        container.setLayout(new qx.ui.layout.Flow(10));
        layoutOptions.flex = 1;
      } else {
        container.setLayout(new qx.ui.layout.VBox());
      }
      Object.entries(properties).forEach(([key, value]) => container.add(this.__expand(key, value, depth+1, `${path}.${key}`)));
      return container;
    },
    /**
     * Uses objectPath library to construct a JS object with the values of the inputs.
     */
    toObject: function() {
      const obj = {};
      Object.entries(this.__inputsMap).forEach(([path, input]) => objectPath.set(obj, path, input.getValue()));
      return obj;
    },
    /**
     * Generates a non-leaf form item.
     * 
     * @param {String} key Current object's key.
     * @param {Object} schema Current schema.
     * @param {Integer} depth Current depth into the schema.
     * @param {Boolean} isArrayItem Used for styling.
     */
    __getHeader: function(key, schema, depth, isArrayItem) {
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      })).set({
        marginBottom: 10
      });
      const labelText = this.__getHeaderText(key, schema, isArrayItem);
      const label = new qx.ui.basic.Label(labelText).set({
        font: depth === 0 ? "title-18" : depth == 1 ? "title-16" : "title-14",
        allowStretchX: true
      });
      header.add(label, {
        flex: isArrayItem ? 0 : 1
      });
      if (isArrayItem) {
        const deleteButton = new qx.ui.form.Button(this.tr("Remove")).set({
          appearance: "link-button"
        });
        header.add(deleteButton);
        deleteButton.addListener("execute", () => {
          const container = header.getLayoutParent();
          const parent = container.getLayoutParent();
          parent.remove(container);
        }, this);
      }
      return header;
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
     * Method that returns an appropriate text for a label.
     */
    __getHeaderText: function(key, schema, isArrayItem) {
      let title = schema.title || key;
      if (isArrayItem) {
        title = schema.title ? `${schema.title} ` : "";
        return title + `#${key}`;
      }
      return title;
    }
  }
});
