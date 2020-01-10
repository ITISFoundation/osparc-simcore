/* ************************************************************************
   Copyright: 2013 OETIKER+PARTNER AG
              2018 ITIS Foundation
   License:   MIT
   Authors:   Tobi Oetiker <tobi@oetiker.ch>
   Utf8Check: äöü
************************************************************************ */

/**
 * Create a form. The argument to the form
 * widget defines the structure of the form.
 *
 * <pre class='javascript'>
 *   {
 *     key: {
 *       displayOrder: 5,
 *       label: "Widget SelectBox Test",
 *       description: "Test Input for SelectBox",
 *       defaultValue: "dog",
 *       type: "string",
 *       widget: {
 *         type: "SelectBox",
 *         structure: [{
 *           key: "dog",
 *           label: "A Dog"
 *         }, {
 *           key: "cat",
 *           label: "A Cat"
 *         }]
 *       }
 *     },
 *   }
 * </pre>
 *
 * The default widgets for data types are as follows:
 *     string: text
 *     integer: spinner
 *     bool:  checkBox
 *     number: text
 *     data:  file-upload/selection
 *
 * The following widget types are supported:
 *     selectBox: { structure: [ {key: x, label: y}, ...] },
 *     date: { }, // following unix tradition, dates are represented in epoc seconds
 *     password: {},
 *     textArea: {},
 *     hiddenText: {},
 *     checkBox: {},
 *     comboBox: {},
 *
 *
 * Populate the new form using the setData method, providing a map
 * with the required data.
 *
 */

qx.Class.define("osparc.component.form.Structure2CtrlField", {
  type: "static",

  statics: {
    getField: function(s) {
      if (s.defaultValue) {
        if (!s.set) {
          s.set = {};
        }
        s.set.value = s.defaultValue;
      }

      if (!s.widget) {
        let type = s.type;
        if (type.match(/^data:/)) {
          type = "data";
        }
        s.widget = {
          type: {
            string: "Text",
            integer: "Spinner",
            number: "Number",
            boolean: "CheckBox",
            data: "FileButton"
          }[type]
        };
      }
      let control;
      let init;
      switch (s.widget.type) {
        case "Date":
          control = new qx.ui.form.DateField();
          init = this.initDateField;
          break;
        case "Text":
          control = new qx.ui.form.TextField();
          init = this.initTextField;
          break;
        case "Number":
          control = new qx.ui.form.TextField();
          init = this.initNumberField;
          break;
        case "Spinner":
          control = new qx.ui.form.Spinner();
          control.set({
            maximum: 10000,
            minimum: -10000
          });
          init = this.initSpinner;
          break;
        case "Password":
          control = new qx.ui.form.PasswordField();
          init = this.initTextField;
          break;
        case "TextArea":
          control = new qx.ui.form.TextArea();
          init = this.initTextArea;
          break;
        case "CheckBox":
          control = new qx.ui.form.CheckBox();
          init = this.initBoolField;
          break;
        case "SelectBox":
          control = new qx.ui.form.SelectBox();
          init = this.initSelectBox;
          break;
        case "ComboBox":
          control = new qx.ui.form.ComboBox();
          init = this.initComboBox;
          break;
        case "FileButton":
          control = new qx.ui.form.TextField();
          init = this.initFileButton;
          break;
        default:
          throw new Error("unknown widget type " + s.widget.type);
      }

      init.call(this, s, control);

      return control;
    },

    initDateField: function(s, control) {
      if (!s.set) {
        s.set = {};
      }
      s.set.dateFormat = new qx.util.format.DateFormat(
        this["tr"](
          s.set.dateFormat ?
            s.set.dateFormat :
            "dd.MM.yyyy"
        )
      );
      let dateValue = s.defaultValue;
      if (dateValue !== null) {
        if (typeof dateValue == "number") {
          s.defaultValue = new Date(dateValue * 1000);
        } else {
          s.defaultValue = new Date(dateValue);
        }
      }
    },

    initTextField: function() {
    },

    initNumberField: function(s, control) {
      if (!s.set) {
        s.set = {};
      }
      if (s.defaultValue) {
        s.set.value = qx.lang.Type.isNumber(s.defaultValue) ? String(s.defaultValue) : s.defaultValue;
      } else {
        s.set.value = String(0);
      }
    },

    initSpinner: function(s, control) {
      if (!s.set) {
        s.set = {};
      }
      if (s.defaultValue) {
        s.set.value = parseInt(String(s.defaultValue));
      } else {
        s.set.value = 0;
      }
    },

    initTextArea: function(s, control) {
      if (s.widget.minHeight) {
        control.setMinHeight(s.widget.minHeight);
      }
    },

    initBoolField: function(s, control) {
      if (!s.set) {
        s.set = {};
      }
    },

    initSelectBox: function() {

    },

    initComboBox: function() {

    },

    initFileButton: function() {

    }
  }
});
