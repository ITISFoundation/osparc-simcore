/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.AnnotationEditor", {
  extend: qx.ui.core.Widget,

  construct: function(annotation) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__form = new qx.ui.form.Form();
    this.getChildControl("form-renderer");

    if (annotation) {
      this.setAnnotation(annotation);
    }
  },

  events: {
    "addAnnotation": "qx.event.type.Event",
    "cancel": "qx.event.type.Event",
    "deleteAnnotation": "qx.event.type.Event",
  },

  properties: {
    annotation: {
      check: "osparc.workbench.Annotation",
      init: null,
      nullable: true,
      apply: "__applyAnnotation"
    },

    marker: {
      check: "Object",
      init: null,
      nullable: true,
      apply: "__applyMarker"
    }
  },

  members: {
    __form: null,

    getForm: function() {
      return this.__form;
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "form-renderer":
          control = new qx.ui.form.renderer.Single(this.__form);
          this._add(control);
          break;
        case "text-field":
          control = new qx.ui.form.TextField();
          this.__form.add(control, "Text", null, "text");
          break;
        case "text-area":
          control = new qx.ui.form.TextArea().set({
            autoSize: true,
            minHeight: 70,
            maxHeight: 140
          });
          this.__form.add(control, "Note", null, "note");
          break;
        case "color-picker":
          control = new osparc.form.ColorPicker();
          this.__form.add(control, "Color", null, "color");
          break;
        case "font-size":
          control = new qx.ui.form.Spinner();
          this.__form.add(control, "Size", null, "size");
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "cancel-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text"
          });
          control.addListener("execute", () => this.fireEvent("cancel"), this);
          buttons.add(control);
          break;
        }
        case "add-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Add")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => this.fireEvent("addAnnotation"), this);
          buttons.add(control);
          break;
        }
        case "delete-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Delete")).set({
            appearance: "danger-button"
          });
          control.addListener("execute", () => this.fireEvent("deleteAnnotation"), this);
          buttons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyAnnotation: function(annotation) {
      if (annotation === null) {
        return;
      }

      const annotationTypes = osparc.workbench.Annotation.TYPES;

      const attrs = annotation.getAttributes();
      if (annotation.getType() === annotationTypes.TEXT) {
        const textField = this.getChildControl("text-field").set({
          value: attrs.text
        });
        textField.addListener("changeValue", e => annotation.setText(e.getData()));
      } else if (annotation.getType() === annotationTypes.NOTE) {
        const textArea = this.getChildControl("text-area").set({
          value: attrs.text
        });
        textArea.addListener("changeValue", e => annotation.setText(e.getData()));
      }

      if ([annotationTypes.TEXT, annotationTypes.RECT].includes(annotation.getType())) {
        const colorPicker = this.getChildControl("color-picker");
        annotation.bind("color", colorPicker, "value");
        colorPicker.bind("value", annotation, "color");
      }

      if (annotation.getType() === annotationTypes.TEXT) {
        const fontSizeField = this.getChildControl("font-size").set({
          value: attrs.fontSize
        })
        fontSizeField.addListener("changeValue", e => annotation.setFontSize(e.getData()));
      }
    },

    __applyMarker: function(marker) {
      if (marker === null) {
        return;
      }

      const colorPicker = this.getChildControl("color-picker");
      marker.bind("color", colorPicker, "value");
      colorPicker.bind("value", marker, "color");
    },

    addDeleteButton: function() {
      this.getChildControl("delete-btn");
    },

    addAddButtons: function() {
      this.getChildControl("cancel-btn");
      this.getChildControl("add-btn");

      // Listen to "Enter" key
      this.addListener("keypress", keyEvent => {
        if (keyEvent.getKeyIdentifier() === "Enter") {
          this.fireEvent("addAnnotation");
        }
      }, this);
    },

    makeItModal: function() {
      this.set({
        padding: 10
      });

      this.show();

      const showEditor = () => this.show();
      const hideEditor = () => this.exclude();
      const tapListener = event => {
        if (osparc.utils.Utils.isMouseOnElement(this, event)) {
          return;
        }
        hideEditor();
        this.set({
          annotation: null,
          marker: null
        });
        document.removeEventListener("mousedown", tapListener);
      };
      showEditor();
      document.addEventListener("mousedown", tapListener);
    }
  }
});
