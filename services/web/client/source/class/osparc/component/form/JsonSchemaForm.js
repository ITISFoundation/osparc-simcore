/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A Qooxdoo generated form using JSONSchema specification.
 */
qx.Class.define("osparc.component.form.JsonSchemaForm", {
  extend: qx.ui.core.Widget,
  construct: function(schemaUrl) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox());
    const ajvLoader = new qx.util.DynamicScriptLoader("https://cdnjs.cloudflare.com/ajax/libs/ajv/6.11.0/ajv.min.js");
    ajvLoader.addListener("ready", e => {
      fetch(schemaUrl)
        .then(response => response.json())
        .then(this.__validateSchema)
        .then(this.__renderForm)
        .catch(err => {
          console.error(err);
          this.__renderForm(null);
        });
    }, this);
    this.__renderForm = this.__renderForm.bind(this);
    this.__validateSchema = this.__validateSchema.bind(this);
    ajvLoader.start();
  },
  events: {
    "ready": "qx.event.type.Event"
  },
  members: {
    __schema: null,
    __renderForm: function(schema) {
      this._removeAll();
      if (schema) {
        this.__schema = schema;
        // Render function
        this._add(this.__expand(null, schema));
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
    __expand: function(key, schema, depth=0) {
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
          Object.entries(schema.properties).forEach(([key, value]) => container.add(this.__expand(key, value, depth+1)));
        } else if (schema.type === "array") {
          container.setAppearance("form-array-container");
          const addButton = new qx.ui.form.Button(`Add ${key}`, "@FontAwesome5Solid/plus-circle/14");
          addButton.addListener("execute", () => container.add(this.__expand(`${key}Item`, schema.items, depth+1)), this);
          header.add(addButton);
        }
      } else {
        container.add(new qx.ui.basic.Label(key));
        switch (schema.type) {
          default:
            container.add(new qx.ui.form.TextField());
        }
      }
      return container;
    }
  }
});
