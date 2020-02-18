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
qx.Class.define("osparc.component.form.JsonSchemaForm", {
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
        this.__add(new qx.ui.basic.Label().set({
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
      const jsonSchemaUrl = schema.$schema;
      return fetch(jsonSchemaUrl)
        .then(response => response.json())
        .then(jsonSchema => {
          const ajv = new Ajv();
          const validate = ajv.compile(jsonSchema);
          if (validate(schema)) {
            return schema;
          } else {
            console.error(ajv.errors);
            return null;
          }
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
          container.setAppearance("form-array-container");
          const addButton = new qx.ui.form.Button(`Add ${key}`, "@FontAwesome5Solid/plus-circle/14");
          addButton.addListener("execute", () => container.add(this.__expand(pos, schema.items, depth+1, `${path}.${pos++}`)), this);
          header.add(addButton);
        }
      } else {
        // Leaf (render input depending on type)
        container.add(new qx.ui.basic.Label(key)); // Input label
        const fixedPath = path.substring(1); // Removes starting point from path
        const input = this.__getInput(schema.type);
        this.__inputsMap[fixedPath] = input; // Keeps a map of the inputs with their paths for later use
        container.add(input);
      }
      return container;
    },
    /**
     * Expands and object property changing its style depending on certain parameters.
     * 
     * @param {Object} properties Object's properties to be expanded.
     * @param {Integer} depth Current depth into the schema.
     * @param {String} path Current result object path.
     * @param {Boolean} isArrayItem Used for different styling.
     */
    __expandObject: function(properties, depth, path, isArrayItem) {
      let container = new qx.ui.container.Composite()
      if (isArrayItem) {
        container.setLayout(new qx.ui.layout.HBox(10));
        Object.entries(properties).forEach(([key, value]) => container.add(this.__expand(key, value, depth+1, `${path}.${key}`), {
          flex: 1
        }));
      } else {
        container.setLayout(new qx.ui.layout.VBox());
        Object.entries(properties).forEach(([key, value]) => container.add(this.__expand(key, value, depth+1, `${path}.${key}`)));
      }
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
     * 
     * @param {String} key Current object's key.
     * @param {Object} schema Current schema.
     * @param {Integer} depth Current depth into the schema.
     * @param {Boolean} isArrayItem Used for styling.
     */
    __getHeader: function(key, schema, depth, isArrayItem) {
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox()).set({
        marginBottom: 10
      });
      const labelText = schema.title || (isArrayItem ? "#" + key : key);
      header.add(new qx.ui.basic.Label(labelText).set({
        font: depth === 0 ? "title-18" : depth == 1 ? "title-16" : "title-14",
        allowStretchX: true
      }), {
        flex: 1
      });
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
    }
  }
});
