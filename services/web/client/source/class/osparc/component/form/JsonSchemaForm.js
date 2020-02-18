/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A Qooxdoo generated form using JSONSchema specification.
 *
 * @asset(object-path/object-path.min.js)
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
      "/resource/object-path/object-path.min.js"
    ]);
    ajvLoader.addListener("ready", e => {
      fetch(schemaUrl)
        .then(response => response.json())
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
    __expand: function(key, schema, depth=0, path="") {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        marginBottom: 10
      });
      if (schema.type === "object" || schema.type === "array") {
        const header = new qx.ui.container.Composite(new qx.ui.layout.HBox());
        header.add(new qx.ui.basic.Label(schema.title || key).set({
          font: depth === 0 ? "title-18" : depth == 1 ? "title-16" : "title-14",
          allowStretchX: true,
          marginBottom: 10
        }), {
          flex: 1
        });
        container.add(header);
        if (schema.type === "object" && schema.properties) {
          Object.entries(schema.properties).forEach(([key, value]) => container.add(this.__expand(key, value, depth+1, `${path}.${key}`)));
        } else if (schema.type === "array") {
          let length = 0;
          container.setAppearance("form-array-container");
          const addButton = new qx.ui.form.Button(`Add ${key}`, "@FontAwesome5Solid/plus-circle/14");
          addButton.addListener("execute", () => container.add(this.__expand(`${key} #${length}`, schema.items, depth+1, `${path}.${length++}`)), this);
          header.add(addButton);
        }
      } else {
        container.add(new qx.ui.basic.Label(key));
        const fixedPath = path.substring(1);
        let input;
        switch (schema.type) {
          default:
            input = new qx.ui.form.TextField();
        }
        this.__inputsMap[fixedPath] = input;
        container.add(input);
      }
      return container;
    },
    toObject: function() {
      const obj = {};
      Object.entries(this.__inputsMap).forEach(([path, input]) => objectPath.set(obj, path, input.getValue()));
      return obj;
    }
  }
});
